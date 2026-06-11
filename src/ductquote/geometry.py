import math
from .models import Point, DuctSegment
from .config import load_settings

_S = load_settings()["geometry"]


def _brightness(c):
    if not c:
        return 0.0
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _is_colored(c):
    if not c:
        return False
    return max(c) - min(c) > 0.15


def extract_lines(page):
    """Return [(Point, Point, color)] of duct-candidate line segments after
    weight / brightness / length filtering (borders, walls, grid removed)."""
    out = []
    for d in page.get_drawings():
        w = d.get("width") or 0.5
        col = d.get("color")
        if w > _S["max_line_weight_pts"]:
            continue
        if col and not _is_colored(col) and _brightness(col) > _S["max_grey_brightness"]:
            continue
        for item in d["items"]:
            if item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            length = math.hypot(p2.x - p1.x, p2.y - p1.y)
            if length < _S["min_line_len_pts"]:
                continue
            out.append((Point(x=p1.x, y=p1.y), Point(x=p2.x, y=p2.y), col))
    return out


def _angle(p1, p2):
    return math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x)) % 180


def _dist2(a, b):
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _gate_by_anchors(lines, anchors, radius):
    if not anchors:
        return lines
    r2 = radius * radius
    gated = []
    for (p1, p2, col) in lines:
        mx, my = (p1.x + p2.x) / 2, (p1.y + p2.y) / 2
        for an in anchors:
            if (mx - an.x) ** 2 + (my - an.y) ** 2 <= r2:
                gated.append((p1, p2, col))
                break
    return gated


def pair_walls(lines, anchors=None, anchor_radius=600.0):
    """Pair parallel duct walls into centerline segments. When `anchors`
    (dimension-label centers) are given, only lines near a label are considered
    — this is both faster (small n) and more precise (real ducts carry sizes)."""
    S = load_settings()["geometry"]
    lines = _gate_by_anchors(lines, anchors, anchor_radius)

    # Pre-compute angle, perpendicular offset, and length-projection interval.
    meta = []
    for (p1, p2, _c) in lines:
        ang = _angle(p1, p2)
        th = math.radians(ang)
        dx, dy = math.cos(th), math.sin(th)
        nx, ny = -dy, dx
        off = p1.x * nx + p1.y * ny
        t1 = p1.x * dx + p1.y * dy
        t2 = p2.x * dx + p2.y * dy
        meta.append((ang, off, min(t1, t2), max(t1, t2)))

    segs = []
    used = set()
    n = len(lines)
    for i in range(n):
        if i in used:
            continue
        ai, offi, ti0, ti1 = meta[i]
        a1, a2, _ = lines[i]
        for j in range(i + 1, n):
            if j in used:
                continue
            aj, offj, tj0, tj1 = meta[j]
            da = abs(ai - aj)
            if min(da, 180 - da) > S["parallel_angle_tol_deg"]:
                continue
            gap = abs(offi - offj)
            if not (S["parallel_gap_min_pts"] <= gap <= S["parallel_gap_max_pts"]):
                continue
            if min(ti1, tj1) - max(ti0, tj0) < 5:   # require length overlap
                continue
            b1, b2, _ = lines[j]
            if _dist2(a1, b1) > _dist2(a1, b2):       # align endpoint order
                b1, b2 = b2, b1
            c1 = Point(x=(a1.x + b1.x) / 2, y=(a1.y + b1.y) / 2)
            c2 = Point(x=(a2.x + b2.x) / 2, y=(a2.y + b2.y) / 2)
            segs.append(DuctSegment(p1=c1, p2=c2, length_pts=math.hypot(c2.x - c1.x, c2.y - c1.y)))
            used.add(i)
            used.add(j)
            break
    return segs
