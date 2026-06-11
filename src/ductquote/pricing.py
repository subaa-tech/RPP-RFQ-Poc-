import math
from .models import LineItem, Shape
from .config import load_catalog


def _dimstr(dim):
    return f"{int(dim.width_in)}x{int(dim.height_in)}" if dim.height_in else f'{int(dim.width_in)}"Ø'


def _gauge_for(longest_in, cat):
    """SMACNA minimum gauge = the heavier of (pressure-class baseline) and
    (size-based minimum). lb/sqft is monotonic with thickness, so 'heavier' = larger lb."""
    pc = cat.get("default_pressure_class_wg", 2.0)
    pg = next((r for r in cat["gauge_by_pressure_class"] if pc <= r["max_wg"]),
              cat["gauge_by_pressure_class"][-1])
    sg = next((r for r in cat["gauge_by_size"] if longest_in <= r["max_dim_in"]),
              cat["gauge_by_size"][-1])
    heavy = pg if pg["lb_per_sqft"] >= sg["lb_per_sqft"] else sg
    why = "pressure-class" if heavy is pg else "size"
    return heavy["gauge"], heavy["lb_per_sqft"], why


def _spiral_rate(dia_in, cat):
    return next((r["usd"] for r in cat["spiral_buyout_per_lf"] if dia_in <= r["max_dia_in"]),
                cat["spiral_buyout_per_lf"][-1]["usd"])


def price_item(li: LineItem, cat=None) -> LineItem:
    """Price a duct/fitting line item. Rectangular -> SMACNA shop-fab chain
    (area->gauge->weight->cost). Round -> spiral vendor buy-out ($/LF by diameter).
    Fully deterministic; every step cited in derivation."""
    cat = cat or load_catalog()

    if li.shape == Shape.ROUND:
        dia = li.width_in
        rate = _spiral_rate(dia, cat)
        li.surface_area_sqft = round(math.pi * (dia / 12.0) * li.length_ft * li.quantity, 2)
        li.gauge = "spiral buy-out"
        li.material_cost = round(li.length_ft * li.quantity * rate, 2)
        li.labor_cost = 0.0
        li.overhead_cost = round(li.material_cost * cat["overhead_rate"], 2)
        li.freight_cost = 0.0
        li.total_cost = round(li.material_cost + li.overhead_cost, 2)
        li.sale_price = round(li.total_cost / (1 - cat["margin_pct"]), 2)
        li.derivation += [
            f'Round {int(dia)}" = spiral vendor buy-out: {li.length_ft} LF x ${rate}/LF = ${li.material_cost}',
            f"Overhead {cat['overhead_rate'] * 100:.0f}% = ${li.overhead_cost}; total ${li.total_cost}; "
            f"sale @ {cat['margin_pct'] * 100:.0f}% margin = ${li.sale_price}",
        ]
        return li

    # Rectangular shop-fabricated
    perim_ft = 2 * (li.width_in + (li.height_in or 0)) / 12.0
    longest = max(li.width_in, li.height_in or 0)
    li.surface_area_sqft = round(perim_ft * li.length_ft * li.quantity, 2)
    gauge, lb_sqft, why = _gauge_for(longest, cat)
    li.gauge = gauge
    raw_w = li.surface_area_sqft * lb_sqft
    up = cat["waste_up_rule_lbs"]
    li.weight_lbs = math.ceil(raw_w / up) * up if raw_w else 0
    li.material_cost = round(li.weight_lbs * cat["material_cost_per_lb"], 2)
    li.labor_cost = round(li.surface_area_sqft * cat["fab_labor_per_sqft"], 2)
    li.overhead_cost = round((li.material_cost + li.labor_cost) * cat["overhead_rate"], 2)
    li.freight_cost = round(li.weight_lbs * cat["freight_per_lb"], 2)
    li.total_cost = round(li.material_cost + li.labor_cost + li.overhead_cost + li.freight_cost, 2)
    li.sale_price = round(li.total_cost / (1 - cat["margin_pct"]), 2)
    li.derivation += [
        f"Perimeter {perim_ft:.2f} ft/ft; Surface area {li.surface_area_sqft} sqft",
        f"Gauge {gauge} (governed by {why}, {lb_sqft} lb/sqft); raw {raw_w:.1f} lb up-ruled to {li.weight_lbs} lb",
        f"Material {li.weight_lbs}lb x ${cat['material_cost_per_lb']}/lb = ${li.material_cost}",
        f"Labor {li.surface_area_sqft}sqft x ${cat['fab_labor_per_sqft']} = ${li.labor_cost}",
        f"Overhead {cat['overhead_rate'] * 100:.0f}% = ${li.overhead_cost}; Freight = ${li.freight_cost}",
        f"Total cost ${li.total_cost}; Sale @ {cat['margin_pct'] * 100:.0f}% margin = ${li.sale_price}",
    ]
    return li


def price_all(items):
    return [price_item(i) for i in items]


def price_fittings(fittings, run_dim_by_id, cat=None):
    """Price each detected fitting by SMACNA equivalent-length on the connected duct's size."""
    cat = cat or load_catalog()
    eq = cat["fitting_equiv_length_ft"]
    out = []
    for f in fittings:
        dim = next((run_dim_by_id[rid] for rid in f.connected_run_ids if rid in run_dim_by_id), None)
        if dim is None:
            continue
        equiv = float(eq.get(f.type.value, 5))
        li = LineItem(
            item_no=0, description=f"{f.type.value.replace('_', ' ')} on {_dimstr(dim)}",
            page_label=f"P{f.page_index + 1}", category="fitting",
            shape=dim.shape, width_in=dim.width_in or 0.0, height_in=dim.height_in, length_ft=equiv,
            derivation=[f"fitting {f.id}: SMACNA equivalent length {equiv} LF on {_dimstr(dim)} duct"],
        )
        price_item(li, cat)
        out.append(li)
    return out


def reprice_items(items_data, margin_pct, cat=None):
    """Re-price a reviewer-edited line-item list deterministically (server-authoritative).
    Honors per-item `included` flags and edited dimensions/length; recomputes the full
    SMACNA chain for ducts/fittings and margin for hardware. Pricing never trusts the client."""
    base = cat or load_catalog()
    cat = dict(base)
    cat["margin_pct"] = float(margin_pct)
    out = []
    for d in items_data:
        if not d.get("included", True):
            continue
        category = d.get("category", "duct")
        if category == "hardware":
            cost = round(float(d.get("material_cost") or d.get("total_cost") or 0.0), 2)
            li = LineItem(
                item_no=0, description=d.get("description", "Hardware"),
                page_label=d.get("page_label", "(all)"), category="hardware",
                quantity=float(d.get("quantity") or 1), material_cost=cost, total_cost=cost,
                sale_price=round(cost / (1 - cat["margin_pct"]), 2),
                derivation=[f"hardware ${cost}; sale @ {cat['margin_pct'] * 100:.0f}% margin"],
            )
        else:
            hi = d.get("height_in")
            hi = float(hi) if hi not in (None, "", 0, "0") else None
            li = LineItem(
                item_no=0, description=d.get("description", ""),
                page_label=d.get("page_label", ""), category=category,
                shape=Shape(d.get("shape", "rect")),
                width_in=float(d.get("width_in") or 0), height_in=hi,
                length_ft=round(float(d.get("length_ft") or 0), 2),
                quantity=float(d.get("quantity") or 1),
            )
            if category == "duct":
                size = f"{int(li.width_in)}x{int(li.height_in)}" if li.height_in else f'{int(li.width_in)}"Ø'
                li.description = f"{li.shape.value} duct {size}, {li.length_ft}ft"
            price_item(li, cat)
        out.append(li)
    for n, li in enumerate(out, 1):
        li.item_no = n
    return {
        "included_items": [i.model_dump() for i in out],
        "subtotal_cost": round(sum(i.total_cost for i in out), 2),
        "total_sale_price": round(sum(i.sale_price for i in out), 2),
        "margin_pct": cat["margin_pct"],
    }


def price_hardware(thumb, cat=None):
    """Price thumb-rule hardware (clamps, bolts) per piece."""
    cat = cat or load_catalog()
    hw = cat["hardware"]
    m = cat["margin_pct"]
    out = []
    specs = [("Duct clamps", int(thumb.get("clamps", 0)), hw["clamp_usd"]),
             ("Hanger bolts", int(thumb.get("bolts", 0)), hw["bolt_usd"])]
    for desc, qty, unit in specs:
        if qty <= 0:
            continue
        cost = round(qty * unit, 2)
        out.append(LineItem(
            item_no=0, description=f"{desc} x{qty}", page_label="(all)", category="hardware",
            shape=Shape.RECT, quantity=qty, material_cost=cost, total_cost=cost,
            sale_price=round(cost / (1 - m), 2),
            derivation=[f"{qty} x ${unit}/ea (thumb rule) = ${cost}; sale @ {m * 100:.0f}% margin"],
        ))
    return out
