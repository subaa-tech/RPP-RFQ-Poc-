from src.ductquote.models import LineItem, Shape
from src.ductquote.pricing import price_item


def test_pricing_chain_rect():
    li = LineItem(item_no=1, description="t", page_label="M-101", shape=Shape.RECT,
                  width_in=24, height_in=12, length_ft=50)
    out = price_item(li)
    assert round(out.surface_area_sqft, 1) == 300.0
    assert out.gauge == "24 ga"
    assert out.weight_lbs > 0
    assert out.sale_price > out.total_cost
    assert any("Surface area" in d for d in out.derivation)
