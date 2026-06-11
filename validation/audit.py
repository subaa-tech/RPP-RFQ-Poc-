"""Exhaustive per-duct AUDIT tool for manual human verification.

For EVERY priced duct (same detection as the quote, via detect_page_ducts), renders a
high-resolution highlighted crop with its dimension label in frame, prices it, runs a
battery of automated condition checks ("prompts"), and writes a self-contained HTML
audit sheet (output/audit/audit.html) where a human ticks each duct correct/wrong by eye.

Usage: python -m validation.audit "<pdf>"
"""
import html
import sys
from pathlib import Path

sys.path.insert(0, ".")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import fitz
from src.ductquote.loader import open_pdf, parse_scale
from src.ductquote.classify import classify_pages
from src.ductquote.config import load_settings, load_catalog
from src.ductquote.pipeline import detect_page_ducts
from src.ductquote.pricing import price_item
from src.ductquote.models import LineItem

OUT = Path("output/audit")
CROPS = OUT / "crops"


def _size(r):
    d = r.dimension
    return f"{int(d.width_in)}x{int(d.height_in)}" if d.height_in else f'{int(d.width_in)}"Ø'


def _conditions(r, li, page_ducts):
    """Automated verification conditions. Each -> (key, ok, label)."""
    d = r.dimension
    w = d.width_in or 0
    h = d.height_in
    longest = max(w, h or 0)
    shortest = min(w, h or w)
    aspect = (longest / shortest) if shortest else 99
    # duplicate proximity (same size, centre within 25 pt)
    cx = sum((s.p1.x + s.p2.x) / 2 for s in r.segments) / len(r.segments)
    cy = sum((s.p1.y + s.p2.y) / 2 for s in r.segments) / len(r.segments)
    dup = False
    for o in page_ducts:
        if o is r:
            continue
        ocx = sum((s.p1.x + s.p2.x) / 2 for s in o.segments) / len(o.segments)
        ocy = sum((s.p1.y + s.p2.y) / 2 for s in o.segments) / len(o.segments)
        if _size(o) == _size(r) and ((cx - ocx) ** 2 + (cy - ocy) ** 2) ** 0.5 < 25:
            dup = True
            break
    even = (int(w) % 2 == 0) and (h is None or int(h) % 2 == 0)
    return [
        ("label", d is not None, "Dimension label read"),
        ("length", 1.0 <= r.length_ft <= 60.0, f"Length plausible (1–60 ft): {r.length_ft}ft"),
        ("stub", r.length_ft >= 1.0, "Not a sub-1ft stub (tag/fitting?)"),
        ("aspect", aspect <= 8, f"Aspect ratio sane (≤8:1): {aspect:.1f}:1"),
        ("conf", r.confidence >= 0.7, f"Detection confidence ≥0.7: {r.confidence:.2f}"),
        ("std", even, "Standard even-inch size"),
        ("dup", not dup, "No same-size duplicate within 25pt"),
    ]


def _crop(doc, r, idx):
    page = doc[r.page_index]
    xs, ys = [], []
    for s in r.segments:
        xs += [s.p1.x, s.p2.x]
        ys += [s.p1.y, s.p2.y]
    if r.dimension and r.dimension.center:
        xs.append(r.dimension.center.x)
        ys.append(r.dimension.center.y)
    m = 80
    rect = fitz.Rect(min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
    annots = []
    for s in r.segments:
        a = page.add_line_annot((s.p1.x, s.p1.y), (s.p2.x, s.p2.y))
        a.set_colors(stroke=(1, 0, 1))
        a.set_border(width=2)
        a.update()
        annots.append(a)
    pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(4.0, 4.0))
    name = f"crop_{idx:03d}.png"
    pix.save(str(CROPS / name))
    for a in annots:
        page.delete_annot(a)
    return name


def main(pdf_path):
    CROPS.mkdir(parents=True, exist_ok=True)
    S = load_settings()
    cat = load_catalog()
    doc = open_pdf(pdf_path)
    pages = classify_pages(doc)
    scale = parse_scale("\n".join(doc[p.index].get_text() for p in pages if p.is_mechanical))

    cards = []
    idx = 0
    for p in pages:
        if not p.is_mechanical:
            continue
        ducts, _f, _d = detect_page_ducts(doc, p.index, p.sheet_label, scale, S, use_llm=False)
        for r in ducts:
            idx += 1
            li = price_item(LineItem(
                item_no=idx, description="", page_label=r.id, shape=r.dimension.shape,
                width_in=r.dimension.width_in or 0, height_in=r.dimension.height_in,
                length_ft=r.length_ft), cat)
            conds = _conditions(r, li, ducts)
            flagged = any(not ok for _k, ok, _l in conds)
            crop = _crop(doc, r, idx)
            cards.append({
                "idx": idx, "sheet": p.sheet_label, "id": r.id, "size": _size(r),
                "len": r.length_ft, "gauge": li.gauge, "price": li.sale_price,
                "deriv": r.reasons + li.derivation, "conds": conds, "flag": flagged, "crop": crop,
            })
    doc.close()
    _write_html(cards)
    flagged = sum(1 for c in cards if c["flag"])
    print(f"Audit written: {OUT / 'audit.html'}")
    print(f"  {len(cards)} ducts · {flagged} auto-flagged for closer human review")


def _write_html(cards):
    rows = []
    for c in cards:
        badges = "".join(
            f'<span class="b {"ok" if ok else "warn"}">{"✓" if ok else "!"} {html.escape(lbl)}</span>'
            for _k, ok, lbl in c["conds"])
        deriv = "".join(f"<li>{html.escape(x)}</li>" for x in c["deriv"])
        rows.append(f'''<div class="card {"flag" if c["flag"] else ""}" data-i="{c["idx"]}" data-flag="{1 if c["flag"] else 0}">
  <img src="crops/{c["crop"]}" loading="lazy">
  <div class="meta">
    <div class="hd">#{c["idx"]} · {html.escape(c["sheet"] or "")} <span class="rid">{html.escape(c["id"])}</span></div>
    <div class="vals">Size <b>{c["size"]}</b> · Length <b>{c["len"]} ft</b> · {html.escape(c["gauge"])} · <b>${c["price"]:.2f}</b></div>
    <div class="conds">{badges}</div>
    <details><summary>cost derivation</summary><ul>{deriv}</ul></details>
    <div class="human">
      <button class="ok">✓ correct</button>
      <button class="bad">✗ wrong</button>
      <input class="note" placeholder="note: wrong size? length? not a duct?">
    </div>
  </div>
</div>''')
    doc_html = f'''<!doctype html><meta charset="utf-8"><title>Duct Takeoff Audit</title>
<style>
body{{font:14px system-ui;margin:0;background:#0b1322;color:#e8eef8}}
header{{position:sticky;top:0;z-index:5;background:#0d1730;border-bottom:1px solid #24314e;padding:14px 22px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}}
header h1{{font-size:16px;margin:0}}
.stat{{font-family:ui-monospace,monospace;font-size:12px;color:#8ba2c2}}
.stat b{{color:#5eead4}} .stat .w{{color:#ff7a7a}}
button.f,button.exp{{background:#16223c;border:1px solid #2c3c5e;color:#cfe;border-radius:8px;padding:7px 12px;cursor:pointer;font-size:12px}}
button.f.on{{border-color:#f6b40a;color:#f6b40a}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;padding:18px 22px}}
.card{{background:#101a2e;border:1px solid #22314e;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}}
.card.flag{{border-color:#7a5a00;box-shadow:inset 0 0 0 1px rgba(246,180,10,.25)}}
.card.ok-h{{border-color:#2f7d5b}} .card.bad-h{{border-color:#a33}}
.card img{{width:100%;background:#fff;display:block;max-height:230px;object-fit:contain}}
.meta{{padding:11px 13px}}
.hd{{font-weight:600;font-size:13px}} .rid{{font-family:ui-monospace,monospace;font-size:10px;color:#5d6f8e}}
.vals{{font-size:12.5px;color:#bcd;margin:5px 0 8px}} .vals b{{color:#fff}}
.conds{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}}
.b{{font-family:ui-monospace,monospace;font-size:10px;padding:3px 6px;border-radius:6px;border:1px solid #24314e}}
.b.ok{{color:#5eead4;border-color:#2f5d52}} .b.warn{{color:#ffcf7a;border-color:#7a5a00;background:rgba(246,180,10,.08)}}
details{{font-size:11px;color:#8ba2c2;margin-bottom:8px}} details ul{{margin:6px 0;padding-left:16px;line-height:1.7}}
.human{{display:flex;gap:6px;align-items:center}}
.human button{{flex:none;border-radius:7px;padding:6px 9px;cursor:pointer;font-size:12px;border:1px solid #2c3c5e;background:#16223c;color:#cfe}}
.human .ok.sel{{background:#1f6f50;border-color:#34d399;color:#eafff6}}
.human .bad.sel{{background:#7a2630;border-color:#ff7a7a;color:#ffeaea}}
.human .note{{flex:1;background:#0b1322;border:1px solid #24314e;border-radius:7px;color:#e8eef8;padding:6px 8px;font-size:11px}}
</style>
<header>
  <h1>🔍 Duct Takeoff Audit — verify each by eye</h1>
  <span class="stat" id="stat"></span>
  <button class="f" id="flagFilter">Show auto-flagged only</button>
  <button class="exp" id="export">⬇ Export verdicts (CSV)</button>
</header>
<div class="grid" id="grid">
{''.join(rows)}
</div>
<script>
const KEY="duct-audit";
const saved=JSON.parse(localStorage.getItem(KEY)||"{{}}");
function apply(card){{const i=card.dataset.i,v=saved[i]||{{}};
  card.classList.toggle("ok-h",v.verdict==="ok");card.classList.toggle("bad-h",v.verdict==="bad");
  card.querySelector(".ok").classList.toggle("sel",v.verdict==="ok");
  card.querySelector(".bad").classList.toggle("sel",v.verdict==="bad");
  if(v.note!==undefined)card.querySelector(".note").value=v.note;}}
function stat(){{const cards=[...document.querySelectorAll(".card")];
  const ok=cards.filter(c=>saved[c.dataset.i]&&saved[c.dataset.i].verdict==="ok").length;
  const bad=cards.filter(c=>saved[c.dataset.i]&&saved[c.dataset.i].verdict==="bad").length;
  const flag=cards.filter(c=>c.dataset.flag==="1").length;
  document.getElementById("stat").innerHTML=`${{cards.length}} ducts · checked <b>${{ok+bad}}</b>/${{cards.length}} · correct <b>${{ok}}</b> · wrong <span class="w">${{bad}}</span> · auto-flagged <b>${{flag}}</b>`;}}
document.querySelectorAll(".card").forEach(card=>{{apply(card);
  card.querySelector(".ok").onclick=()=>{{set(card,"ok");}};
  card.querySelector(".bad").onclick=()=>{{set(card,"bad");}};
  card.querySelector(".note").oninput=e=>{{const i=card.dataset.i;saved[i]=saved[i]||{{}};saved[i].note=e.target.value;localStorage.setItem(KEY,JSON.stringify(saved));}};
}});
function set(card,v){{const i=card.dataset.i;saved[i]=saved[i]||{{}};saved[i].verdict=(saved[i].verdict===v?null:v);localStorage.setItem(KEY,JSON.stringify(saved));apply(card);stat();}}
let only=false;
document.getElementById("flagFilter").onclick=e=>{{only=!only;e.target.classList.toggle("on",only);
  document.querySelectorAll(".card").forEach(c=>c.style.display=(only&&c.dataset.flag!=="1")?"none":"");}};
document.getElementById("export").onclick=()=>{{let csv="idx,verdict,note\\n";
  document.querySelectorAll(".card").forEach(c=>{{const v=saved[c.dataset.i]||{{}};csv+=`${{c.dataset.i}},${{v.verdict||""}},"${{(v.note||"").replace(/"/g,'""')}}"\\n`;}});
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{{type:"text/csv"}}));a.download="audit_verdicts.csv";a.click();}};
stat();
</script>'''
    (OUT / "audit.html").write_text(doc_html, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
