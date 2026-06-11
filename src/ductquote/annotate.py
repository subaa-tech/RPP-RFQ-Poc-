import fitz
from .models import SystemType

_COLOR = {
    SystemType.SUPPLY: (0, 0, 1),
    SystemType.RETURN: (0, 0.6, 0),
    SystemType.EXHAUST: (1, 0, 0),
    SystemType.UNKNOWN: (1, 0.5, 0),
}

_TARGET_PX = 1600.0   # longest-side target for rendered sheet


def annotate_page(doc, page_index, runs, fittings, out_path):
    """Draw run centerlines (colored by system) + labels + fitting markers,
    render the page to a right-sized PNG (KT-mandated visual proof)."""
    page = doc[page_index]
    shape = page.new_shape()
    for r in runs:
        col = _COLOR.get(r.system, (1, 0.5, 0))
        for s in r.segments:
            shape.draw_line((s.p1.x, s.p1.y), (s.p2.x, s.p2.y))
        shape.finish(color=col, width=2.5)
        mid = r.segments[len(r.segments) // 2]
        lx = (mid.p1.x + mid.p2.x) / 2
        ly = (mid.p1.y + mid.p2.y) / 2
        dim = r.dimension.raw_text if r.dimension else "?"
        page.insert_text((lx + 2, ly - 2), f"{dim} {r.length_ft}ft", fontsize=7, color=col)
    for f in fittings:
        shape.draw_circle((f.location.x, f.location.y), 5)
    if fittings:
        shape.finish(color=(0.6, 0, 0.6), width=1.5)
    if runs or fittings:
        shape.commit()
    zoom = max(0.4, min(2.0, _TARGET_PX / max(page.rect.width, page.rect.height)))
    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(out_path)
    return out_path
