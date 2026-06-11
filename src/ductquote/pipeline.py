import os
from .config import load_env, load_settings, load_catalog
from .loader import open_pdf, parse_scale, _SCALE_RE
from .classify import classify_pages
from .vision_validate import validate_mechanical
from .geometry import extract_lines, pair_walls
from .runs import build_runs
from .dimensions import extract_dim_labels, match_dims_to_runs
from .vision_dims import fill_missing_dims
from .fittings import detect_fittings
from .runsplit import split_ducts_by_size
from .annotate import annotate_page
from .boq import build_boq
from .pricing import price_all, price_fittings, price_hardware
from .quote import assemble_quote, write_outputs
from .review import build_review_report
from .llm import make_client, NullClient


def _is_label_fragment(r, max_len_ft=1.5, max_dist_pts=15.0):
    """A tiny run whose centroid sits ON its own dimension label is a mis-trace of the
    label area, not a real duct beside the label. (Real short stubs sit offset from the label.)"""
    if r.length_ft >= max_len_ft or not r.dimension or not r.dimension.center:
        return False
    cx = sum((s.p1.x + s.p2.x) / 2 for s in r.segments) / len(r.segments)
    cy = sum((s.p1.y + s.p2.y) / 2 for s in r.segments) / len(r.segments)
    dist = ((cx - r.dimension.center.x) ** 2 + (cy - r.dimension.center.y) ** 2) ** 0.5
    return dist < max_dist_pts


def detect_page_ducts(doc, p_index, sheet_label, scale, S, client=None, use_llm=False):
    """Detect priced-ready ducts + fittings for one page (single source of truth used
    by both run_pipeline and the audit tool, so they never drift)."""
    page = doc[p_index]
    if _SCALE_RE.search(page.get_text()) is None:
        return [], [], []      # not a scaled floor plan
    lines = extract_lines(page)
    dims = extract_dim_labels(page)
    W, H = page.rect.width, page.rect.height
    dims = [d for d in dims if d.center
            and d.center.x <= S["match"]["drawing_right_frac"] * W
            and d.center.y <= S["match"]["drawing_bottom_frac"] * H]
    if not dims:
        return [], [], []
    anchors = [d.center for d in dims if d.center]
    segs = pair_walls(lines, anchors=anchors)
    runs = build_runs(segs, scale, p_index, sheet_label or f"M-Page{p_index + 1}")
    runs = match_dims_to_runs(runs, dims, S["match"]["size_radius_pts"])
    max_len = S.get("max_run_len_ft", 120.0)
    min_len = S.get("min_run_len_ft", 0.5)
    ducts = [r for r in runs if r.dimension and min_len <= r.length_ft <= max_len]
    # drop label-fragment mis-traces (tiny run sitting on its own dimension label)
    ducts = [r for r in ducts if not _is_label_fragment(r)]
    ducts = fill_missing_dims(doc if use_llm else None, ducts, client=client,
                              cutoff=S["confidence"]["review_cutoff"])
    fittings = detect_fittings(ducts)
    ducts = split_ducts_by_size(ducts, dims, perp_radius=S["match"]["split_perp_radius_pts"])
    ducts = [d for d in ducts if d.length_ft >= min_len]
    return ducts, fittings, dims


def run_pipeline(pdf_path, project, out_dir="output", use_llm=True):
    load_env()
    S = load_settings()
    cutoff = S["confidence"]["review_cutoff"]
    client = make_client() if use_llm else NullClient()
    os.makedirs(out_dir, exist_ok=True)

    doc = open_pdf(pdf_path)
    pages = classify_pages(doc)
    scale = parse_scale("\n".join(doc[p.index].get_text() for p in pages if p.is_mechanical) or "")
    pages = validate_mechanical(doc if use_llm else None, pages, client=client)
    mech = [p for p in pages if p.is_mechanical]

    all_runs = []
    all_fittings = []
    for p in mech:
        ducts, fittings, _dims = detect_page_ducts(doc, p.index, p.sheet_label, scale, S,
                                                   client=client, use_llm=use_llm)
        if not ducts:
            continue
        annotate_page(doc, p.index, ducts, fittings,
                      os.path.join(out_dir, f"annotated_p{p.index + 1}.png"))
        all_runs += ducts
        all_fittings += fittings

    cat = load_catalog()
    duct_items, thumb = build_boq(all_runs)
    duct_items = price_all(duct_items)
    run_dim = {r.id: r.dimension for r in all_runs if r.dimension}
    fitting_items = price_fittings(all_fittings, run_dim, cat)
    hardware_items = price_hardware(thumb, cat)
    items = duct_items + fitting_items + hardware_items
    for n, li in enumerate(items, 1):
        li.item_no = n
    fsum = {}
    for f in all_fittings:
        fsum[f.type.value] = fsum.get(f.type.value, 0) + 1
    fsum.update({"clamps": thumb["clamps"], "bolts": thumb["bolts"]})
    low = [r.id for r in all_runs if r.confidence < cutoff]
    q = assemble_quote(project, scale, [p.sheet_label for p in mech], items, fsum, low,
                       margin_pct=cat["margin_pct"])
    write_outputs(q, out_dir)
    with open(os.path.join(out_dir, "review_report.md"), "w", encoding="utf-8") as fh:
        fh.write(build_review_report(all_runs, cutoff))
    return q
