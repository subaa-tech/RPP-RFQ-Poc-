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
from .annotate import annotate_page
from .boq import build_boq
from .pricing import price_all, price_fittings, price_hardware
from .quote import assemble_quote, write_outputs
from .review import build_review_report
from .llm import make_client, NullClient


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
        page = doc[p.index]
        # Take off only from SCALED floor-plan sheets; skip schedule/detail/cover sheets.
        if _SCALE_RE.search(page.get_text()) is None:
            continue
        lines = extract_lines(page)
        dims = extract_dim_labels(page)
        # Drawing-area only: drop labels in the title-block / keyed-notes / schedule strip
        # so legend/schedule text can never anchor a false duct run.
        W, H = page.rect.width, page.rect.height
        rfrac = S["match"]["drawing_right_frac"]
        bfrac = S["match"]["drawing_bottom_frac"]
        dims = [d for d in dims if d.center and d.center.x <= rfrac * W and d.center.y <= bfrac * H]
        if not dims:
            continue  # no duct sizes on this sheet -> nothing to take off
        anchors = [d.center for d in dims if d.center]
        segs = pair_walls(lines, anchors=anchors)
        runs = build_runs(segs, scale, p.index, p.sheet_label or f"M-Page{p.index + 1}")
        runs = match_dims_to_runs(runs, dims, S["match"]["size_radius_pts"])
        # real ducts = label-claimed runs within a plausible single-run length (drop table/border lines)
        max_len = S.get("max_run_len_ft", 120.0)
        ducts = [r for r in runs if r.dimension and r.length_ft <= max_len]
        ducts = fill_missing_dims(doc if use_llm else None, ducts, client=client, cutoff=cutoff)
        fittings = detect_fittings(ducts)
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
