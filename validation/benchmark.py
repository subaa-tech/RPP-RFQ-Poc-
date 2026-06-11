"""Accuracy benchmark / certification against validation/ground_truth.yaml.

Ground truth = the estimator's duct-size labels (independent full-text extraction;
see build_ground_truth.py). We certify the DUCT TAKEOFF:
  - M-series sheet segregation (recall / precision)
  - dimension size coverage per sheet (recall = sizes found / present)
  - dimension precision (pipeline sizes that are real labels)
Length is reported (total LF) but flagged: it is geometrically exact per traced run,
yet association-dependent and not independently certified without a reference takeoff.
"""
import re
import yaml
from pathlib import Path

_PAGE_RE = re.compile(r"-P(\d+)\b")


def score_lengths(gt_runs, got_runs):
    if not gt_runs:
        return 1.0
    hits = 0
    for g in gt_runs:
        match = next((r for r in got_runs
                      if r["sheet"] == g["sheet"] and r["dimension"] == g["dimension"]), None)
        if match and abs(match["length_ft"] - g["length_ft_expected"]) <= g["length_tolerance_ft"]:
            hits += 1
    return hits / len(gt_runs)


def score_pages(expected, found):
    es, fs = set(expected), set(found)
    if not es:
        return 1.0, 1.0
    tp = len(es & fs)
    prec = tp / len(fs) if fs else 0.0
    rec = tp / len(es)
    return prec, rec


def _item_size(i):
    if i.height_in:
        return f"{int(i.width_in)}x{int(i.height_in)}"
    return f"{int(i.width_in)}rd"


def _item_page(i):
    m = _PAGE_RE.search(i.page_label)
    return int(m.group(1)) if m else None


def run_benchmark(pdf_path, gt_path="validation/ground_truth.yaml", out_dir="output", use_llm=False):
    gt = yaml.safe_load(Path(gt_path).read_text(encoding="utf-8"))
    from src.ductquote.pipeline import run_pipeline
    q = run_pipeline(pdf_path, gt["project"], out_dir, use_llm=use_llm)

    # 1) M-sheet segregation
    page_prec, page_rec = score_pages(gt.get("mechanical_pages", []), q.mechanical_pages)

    # 2/3) dimension coverage + precision, per duct sheet (keyed by page number)
    got_by_page = {}
    for i in q.line_items:
        pg = _item_page(i)
        got_by_page.setdefault(pg, set()).add(_item_size(i))

    rows = []
    tot_gt = tot_found = tot_got = tot_got_real = 0
    for ds in gt.get("duct_sheets", []):
        pg = ds["page"]
        gt_sizes = set(ds["distinct_sizes"])
        got_sizes = got_by_page.get(pg, set())
        found = gt_sizes & got_sizes
        real = got_sizes & gt_sizes
        tot_gt += len(gt_sizes)
        tot_found += len(found)
        tot_got += len(got_sizes)
        tot_got_real += len(real)
        rows.append({
            "page": pg, "sheet": ds["sheet"],
            "gt_sizes": len(gt_sizes), "found": len(found),
            "recall": round(len(found) / len(gt_sizes), 3) if gt_sizes else 1.0,
            "missed": sorted(gt_sizes - got_sizes),
            "extra": sorted(got_sizes - gt_sizes),
        })

    size_recall = tot_found / tot_gt if tot_gt else 0.0
    size_precision = tot_got_real / tot_got if tot_got else 0.0
    total_lf = round(sum(i.length_ft for i in q.line_items), 1)

    report = _format_report(gt, q, page_prec, page_rec, rows, size_recall, size_precision, total_lf)
    Path(out_dir, "ACCURACY_REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return {
        "page_precision": page_prec, "page_recall": page_rec,
        "dimension_size_recall": round(size_recall, 3),
        "dimension_precision": round(size_precision, 3),
        "line_items": len(q.line_items), "total_lf": total_lf,
    }


def _format_report(gt, q, page_prec, page_rec, rows, size_recall, size_precision, total_lf):
    L = []
    L.append("# Accuracy Certification — RFP/RFQ Vortex Sample POC")
    L.append("")
    L.append(f"**Project:** {gt['project']}")
    L.append(f"**Ground truth:** {gt.get('source', 'estimator duct-size labels')}")
    L.append("")
    L.append("## 1 · M-series sheet segregation")
    L.append(f"- Recall **{page_rec*100:.1f}%** · Precision **{page_prec*100:.1f}%** "
             f"({len(q.mechanical_pages)} sheets identified)")
    L.append("- Note: this dataset is an all-mechanical extract (no A/E/S sheets to reject), "
             "so segregation is necessarily near-trivial here.")
    L.append("")
    L.append("## 2 · Duct dimension takeoff (the core metric)")
    L.append(f"- **Size coverage (recall): {size_recall*100:.1f}%** — distinct duct sizes captured vs present")
    L.append(f"- **Dimension precision: {size_precision*100:.1f}%** — captured sizes that are real labels")
    L.append(f"- Line items: {len(q.line_items)} · Total measured length: {total_lf} LF · "
             f"Quote: ${q.total_sale_price:,.2f}")
    L.append("")
    L.append("| Page | Sheet | GT sizes | Found | Recall | Missed | Extra |")
    L.append("|------|-------|----------|-------|--------|--------|-------|")
    for r in rows:
        L.append(f"| {r['page']} | {r['sheet']} | {r['gt_sizes']} | {r['found']} | "
                 f"{r['recall']*100:.0f}% | {', '.join(r['missed']) or '—'} | {', '.join(r['extra']) or '—'} |")
    L.append("")
    L.append("## 3 · Length")
    L.append(f"- Total measured length **{total_lf} LF**. Lengths are geometrically exact for each "
             "traced run (PyMuPDF coordinates × verified 1/8\"=1'-0\" scale), but depend on correct "
             "wall-pair association and may be conservative for very long ducts (anchor-radius gating).")
    L.append("- Independent length certification needs a reference takeoff (Trimble) or manual measurement.")
    L.append("")
    verdict = "CERTIFIED (>=95%)" if size_recall >= 0.95 else f"{size_recall*100:.1f}% (below 95% target)"
    L.append(f"## Verdict - dimension size coverage: {verdict}")
    L.append("")
    L.append("_Scope: 'size coverage' = distinct duct sizes present on the floor plans that the "
             "takeoff captured. It certifies dimension reading + detection of each duct size, not "
             "per-duct-instance counts or length (those need a reference takeoff)._")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    use_llm = "--llm" in sys.argv
    pdf = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    run_benchmark(pdf, use_llm=use_llm)
