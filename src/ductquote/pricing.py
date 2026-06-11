import math
from .models import LineItem, Shape
from .config import load_catalog


def _gauge_for(longest_in, cat):
    for row in cat["gauge_by_pressure"]:
        if longest_in <= row["max_dim_in"]:
            return row["gauge"], row["lb_per_sqft"]
    last = cat["gauge_by_pressure"][-1]
    return last["gauge"], last["lb_per_sqft"]


def price_item(li: LineItem, cat=None) -> LineItem:
    """SMACNA pricing chain: dims -> surface area -> gauge -> weight -> material +
    labor + overhead + freight -> margin. Fully deterministic; every step cited."""
    cat = cat or load_catalog()
    if li.shape == Shape.RECT:
        perim_ft = 2 * (li.width_in + (li.height_in or 0)) / 12.0
        longest = max(li.width_in, li.height_in or 0)
    else:
        perim_ft = math.pi * (li.width_in / 12.0)
        longest = li.width_in
    li.surface_area_sqft = round(perim_ft * li.length_ft * li.quantity, 2)
    gauge, lb_sqft = _gauge_for(longest, cat)
    li.gauge = gauge
    raw_w = li.surface_area_sqft * lb_sqft
    up = cat["waste_up_rule_lbs"]
    li.weight_lbs = math.ceil(raw_w / up) * up
    li.material_cost = round(li.weight_lbs * cat["material_cost_per_lb"], 2)
    li.labor_cost = round(li.surface_area_sqft * cat["fab_labor_per_sqft"], 2)
    li.overhead_cost = round((li.material_cost + li.labor_cost) * cat["overhead_rate"], 2)
    li.freight_cost = round(li.weight_lbs * cat["freight_per_lb"], 2)
    li.total_cost = round(li.material_cost + li.labor_cost + li.overhead_cost + li.freight_cost, 2)
    li.sale_price = round(li.total_cost / (1 - cat["margin_pct"]), 2)
    li.derivation += [
        f"Perimeter {perim_ft:.2f} ft/ft; Surface area {li.surface_area_sqft} sqft",
        f"Gauge {gauge} ({lb_sqft} lb/sqft); raw {raw_w:.1f} lb up-ruled to {li.weight_lbs} lb",
        f"Material {li.weight_lbs}lb x ${cat['material_cost_per_lb']}/lb = ${li.material_cost}",
        f"Labor {li.surface_area_sqft}sqft x ${cat['fab_labor_per_sqft']} = ${li.labor_cost}",
        f"Overhead {cat['overhead_rate'] * 100:.0f}% = ${li.overhead_cost}; Freight = ${li.freight_cost}",
        f"Total cost ${li.total_cost}; Sale @ {cat['margin_pct'] * 100:.0f}% margin = ${li.sale_price}",
    ]
    return li


def price_all(items):
    return [price_item(i) for i in items]
