from pathlib import Path
from jinja2 import Template
from .models import Quotation


def assemble_quote(project, scale, mech_pages, items, fittings_summary, low_conf, margin_pct):
    sub = round(sum(i.total_cost for i in items), 2)
    total = round(sum(i.sale_price for i in items), 2)
    return Quotation(
        project_name=project, scale=scale, mechanical_pages=mech_pages,
        line_items=items, fittings_summary=fittings_summary, subtotal_cost=sub,
        margin_pct=margin_pct, total_sale_price=total, low_confidence_items=list(low_conf),
    )


def write_outputs(q: Quotation, out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "quote.json").write_text(q.model_dump_json(indent=2), encoding="utf-8")
    tmpl = Template(Path(__file__).parent.joinpath("templates/quote.html.j2").read_text(encoding="utf-8"))
    (out / "quote.html").write_text(tmpl.render(q=q), encoding="utf-8")
    rows = ["item_no,description,page,length_ft,surface_area_sqft,gauge,weight_lbs,total_cost,sale_price"]
    rows += [
        f"{i.item_no},{i.description},{i.page_label},{i.length_ft},{i.surface_area_sqft},"
        f"{i.gauge},{i.weight_lbs},{i.total_cost},{i.sale_price}"
        for i in q.line_items
    ]
    (out / "boq.csv").write_text("\n".join(rows), encoding="utf-8")
