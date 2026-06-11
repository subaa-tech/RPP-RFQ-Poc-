"""Generate an INDEPENDENT, methodologically-fair ground truth for the sample PDF.

Authoritative source = the duct-size labels the estimator placed on the drawing.
A duct TAKEOFF covers the duct **floor-plan** sheets, measuring labels in the **drawing
area** — not the title-block schedule column, and not schedule/legend sheets. So we:
  - keep only sheets whose title-block says "PLAN" (exclude SCHEDULE/DETAIL sheets),
  - exclude labels in the right title-block strip (x > 0.78 * page width) and the
    bottom title block (y > 0.93 * height) — that strip holds the side schedule table.

Writes validation/ground_truth.yaml.

Usage: python -m validation.build_ground_truth "<pdf>"
"""
import sys
import collections
from pathlib import Path

sys.path.insert(0, ".")
import yaml
from src.ductquote.loader import open_pdf, _SCALE_RE
from src.ductquote.classify import classify_pages
from src.ductquote.dimensions import extract_dim_labels

RIGHT_STRIP = 0.78    # exclude title-block / side-schedule column
BOTTOM_STRIP = 0.93   # exclude bottom title block


def _size(d):
    return f"{int(d.width_in)}x{int(d.height_in)}" if d.height_in else f"{int(d.width_in)}rd"


def main(pdf_path):
    doc = open_pdf(pdf_path)
    pages = classify_pages(doc)
    gt_pages = [p.sheet_label for p in pages if p.is_mechanical]
    duct_sheets = []
    for p in pages:
        page = doc[p.index]
        W, H = page.rect.width, page.rect.height
        # A duct floor plan is a SCALED drawing; schedule/legend sheets carry no drawing scale.
        is_plan = _SCALE_RE.search(page.get_text()) is not None
        if not (p.is_mechanical and is_plan):
            continue
        labels = extract_dim_labels(page)
        plan_sizes = [
            _size(d) for d in labels
            if d.center and d.center.x <= RIGHT_STRIP * W and d.center.y <= BOTTOM_STRIP * H
        ]
        if not plan_sizes:
            continue
        duct_sheets.append({
            "page": p.index + 1,
            "sheet": p.sheet_label,
            "title": (p.title or "").strip()[:40],
            "distinct_sizes": sorted(set(plan_sizes)),
            "size_counts": dict(collections.Counter(plan_sizes)),
            "total_labels": len(plan_sizes),
        })
    gt = {
        "project": "GIA Moorefield - PKG 1",
        "source": "independent extraction of estimator duct-size labels, drawing-area only "
                  "(title-block/schedule strip excluded), duct floor-plan sheets only",
        "mechanical_pages": gt_pages,
        "duct_sheets": duct_sheets,
    }
    Path("validation/ground_truth.yaml").write_text(yaml.safe_dump(gt, sort_keys=False), encoding="utf-8")
    print("Ground truth written: validation/ground_truth.yaml")
    print(f"  mechanical pages: {len(gt_pages)}")
    print(f"  duct FLOOR-PLAN sheets: {len(duct_sheets)}")
    for ds in duct_sheets:
        print(f"  p{ds['page']} {ds['sheet']} [{ds['title']}]: "
              f"{len(ds['distinct_sizes'])} distinct, {ds['total_labels']} plan labels")
    doc.close()


if __name__ == "__main__":
    main(sys.argv[1])
