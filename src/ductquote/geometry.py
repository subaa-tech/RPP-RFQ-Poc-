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


def _perp_gap(a1, a2, b1):
    dx, dy = a2.x - a1.x, a2.y - a1.y
    L = math.hypot(dx, dy) or 1e-9
    return abs((b1.x - a1.x) * dy - (b1.y - a1.y) * dx) / L


def pair_walls(lines):
    """Pair parallel walls within gap/angle tolerance into centerline segments."""
    S = load_settings()["geometry"]
    segs = []
    used = set()
    for i in range(len(lines)):
        if i in used:
            continue
        a1, a2, _ = lines[i]
        ang_a = _angle(a1, a2)
        for j in range(i + 1, len(lines)):
            if j in used:
                continue
            b1, b2, _ = lines[j]
            ang_b = _angle(b1, b2)
            if min(abs(ang_a - ang_b), 180 - abs(ang_a - ang_b)) > S["parallel_angle_tol_deg"]:
                continue
            gap = _perp_gap(a1, a2, b1)
            if not (S["parallel_gap_min_pts"] <= gap <= S["parallel_gap_max_pts"]):
                continue
            c1 = Point(x=(a1.x + b1.x) / 2, y=(a1.y + b1.y) / 2)
            c2 = Point(x=(a2.x + b2.x) / 2, y=(a2.y + b2.y) / 2)
            segs.append(DuctSegment(p1=c1, p2=c2, length_pts=math.hypot(c2.x - c1.x, c2.y - c1.y)))
            used.add(i)
            used.add(j)
            break
    return segs
