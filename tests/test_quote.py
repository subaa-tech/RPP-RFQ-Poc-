from src.ductquote.models import LineItem, Shape, Scale
from src.ductquote.quote import assemble_quote


def test_assemble_totals():
    items = [LineItem(item_no=1, description="d", page_label="M-101", shape=Shape.RECT,
                      width_in=24, height_in=12, length_ft=50, total_cost=443.20, sale_price=590.93)]
    q = assemble_quote("GIA Moorefield", Scale(raw="", points_to_feet=1 / 9, source="default"),
                       ["M-101"], items, {"elbow_90": 2}, {}, margin_pct=0.25)
    assert round(q.total_sale_price, 2) == 590.93 and q.fittings_summary["elbow_90"] == 2
