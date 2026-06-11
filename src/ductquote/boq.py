import math
from .models import LineItem
from .config import load_catalog


def build_boq(runs):
    """Turn dimensioned runs into LineItems (no pricing yet). Apply thumb rules
    (clamps every ~2m, 4 bolts/clamp). Runs without a dimension are skipped."""
    cat = load_catalog()
    tr = cat["thumb_rules"]
    items = []
    total_len = 0.0
    n = 0
    for r in runs:
        if not r.dimension:
            continue
        n += 1
        d = r.dimension
        total_len += r.length_ft
        size = f"{int(d.width_in)}" + (f"x{int(d.height_in)}" if d.height_in else '"Ø')
        desc = f"{d.shape.value} duct {size}, {r.length_ft}ft"
        items.append(LineItem(
            item_no=n, description=desc, page_label=r.id.rsplit("-R", 1)[0],
            shape=d.shape, width_in=d.width_in, height_in=d.height_in, length_ft=r.length_ft,
            derivation=[f"run {r.id}: {r.length_ft}ft"] + r.reasons,
        ))
    clamps = math.ceil(total_len / tr["duct_clamp_spacing_ft"]) if total_len else 0
    thumb = {"clamps": clamps, "bolts": clamps * tr["bolts_per_clamp"]}
    return items, thumb
