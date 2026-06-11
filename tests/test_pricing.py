from src.ductquote.models import LineItem, Shape, Dimension, Fitting, FittingType, Point
from src.ductquote.pricing import price_item, price_fittings, price_hardware


def test_pricing_chain_rect():
    li = LineItem(item_no=1, description="t", page_label="M-101", shape=Shape.RECT,
                  width_in=24, height_in=12, length_ft=50)
    out = price_item(li)
    assert round(out.surface_area_sqft, 1) == 300.0
    assert out.gauge == "24 ga"                 # 2" w.g. baseline governs a 24" duct
    assert out.weight_lbs > 0
    assert out.sale_price > out.total_cost
    assert any("Surface area" in d for d in out.derivation)


def test_gauge_size_governs_for_large_duct():
    li = LineItem(item_no=1, description="d", page_label="M", shape=Shape.RECT,
                  width_in=60, height_in=20, length_ft=10)
    out = price_item(li)
    # longest 60" -> size min 22 ga; pressure baseline (2" w.g.) 24 ga; heavier = 22 ga
    assert out.gauge == "22 ga"


def test_round_spiral_buyout():
    li = LineItem(item_no=1, description="r", page_label="M", shape=Shape.ROUND,
                  width_in=12, length_ft=40)
    out = price_item(li)
    assert out.gauge == "spiral buy-out"
    assert out.material_cost == 260.0           # 40 LF x $6.50/LF (12" dia)
    assert out.labor_cost == 0.0
    assert out.sale_price > out.total_cost


def test_fitting_pricing():
    dim = Dimension(shape=Shape.RECT, width_in=14, height_in=12)
    f = Fitting(id="F1", page_index=3, type=FittingType.ELBOW_90,
                location=Point(x=0, y=0), connected_run_ids=["R1"])
    items = price_fittings([f], {"R1": dim})
    assert len(items) == 1
    assert items[0].category == "fitting" and items[0].length_ft == 10  # elbow_90 equiv = 10 LF
    assert items[0].sale_price > 0


def test_hardware_pricing():
    items = price_hardware({"clamps": 10, "bolts": 40})
    assert len(items) == 2
    assert items[0].category == "hardware" and items[0].total_cost == 35.0   # 10 x $3.50
    assert items[1].total_cost == 6.0                                        # 40 x $0.15
