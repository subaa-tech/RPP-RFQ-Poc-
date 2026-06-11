"""Vision cross-check harness (KT dual-read / correction-loop).

Renders high-resolution crops of a sample of detected duct runs, each highlighted in
magenta with its dimension label in frame, so an INDEPENDENT vision reader can verify the
deterministic takeoff: does the visible W x H label match the pipeline's computed size,
and does the highlight really trace a duct (two parallel walls)?

Usage: python -m validation.vision_check "<pdf>" [N]
Writes output/vision_check/crop_*.png and prints a manifest of computed values.
"""
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
from src.ductquote.geometry import extract_lines, pair_walls
from src.ductquote.dimensions import extract_dim_labels, match_dims_to_runs
from src.ductquote.runs import build_runs
from src.ductquote.config import load_settings


def _size(r):
    d = r.dimension
    return f"{int(d.width_in)}x{int(d.height_in)}" if d.height_in else f"{int(d.width_in)}rd"


def main(pdf_path, n=8):
    S = load_settings()
    out = Path("output/vision_check")
    out.mkdir(parents=True, exist_ok=True)
    doc = open_pdf(pdf_path)
    pages = classify_pages(doc)
    scale = parse_scale("\n".join(doc[p.index].get_text() for p in pages if p.is_mechanical))

    ducts = []
    for p in pages:
        if not (p.sheet_label or "").startswith("M-2"):   # the duct floor plans
            continue
        page = doc[p.index]
        lines = extract_lines(page)
        dims = extract_dim_labels(page)
        W, H = page.rect.width, page.rect.height
        dims = [d for d in dims if d.center
                and d.center.x <= S["match"]["drawing_right_frac"] * W
                and d.center.y <= S["match"]["drawing_bottom_frac"] * H]
        anchors = [d.center for d in dims if d.center]
        segs = pair_walls(lines, anchors=anchors)
        runs = build_runs(segs, scale, p.index, p.sheet_label)
        runs = match_dims_to_runs(runs, dims, S["match"]["size_radius_pts"])
        ducts += [r for r in runs if r.dimension]

    ducts.sort(key=lambda r: r.length_ft)
    if not ducts:
        print("no ducts")
        return
    picks = sorted({int(i * (len(ducts) - 1) / (n - 1)) for i in range(n)})
    sample = [ducts[i] for i in picks]

    print(f"sampled {len(sample)} of {len(ducts)} ducts across M-2.x plans\n")
    print("idx | run id | COMPUTED size | COMPUTED len | crop")
    for k, r in enumerate(sample, 1):
        page = doc[r.page_index]
        xs, ys = [], []
        for s in r.segments:
            xs += [s.p1.x, s.p2.x]
            ys += [s.p1.y, s.p2.y]
        if r.dimension.center:
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
        cp = out / f"crop_{k:02d}.png"
        pix.save(str(cp))
        for a in annots:
            page.delete_annot(a)
        print(f"{k:02d} | {r.id} | {_size(r)} | {round(r.length_ft, 1)}ft | {cp.name}")
    doc.close()


if __name__ == "__main__":
    pdf = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(pdf, n)
