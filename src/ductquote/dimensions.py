import re
import math
from .models import Dimension, Shape, Point

# Note: deliberately uses x / X / × only (NOT "/") so the scale text "1/8\"" is
# never mis-parsed as a 1x8 duct dimension.
_RECT = re.compile(r'(?<!\d)(\d{1,3})\s*["”]?\s*[x×X]\s*(\d{1,3})(?!\d)\s*["”]?')
_ROUND = re.compile(r'(?<!\d)(\d{1,3})\s*["”]?\s*(?:[Ø⌀]|dia\.?|DIA)')


def parse_dim(text: str, center: Point | None = None) -> Dimension | None:
    mr = _ROUND.search(text)
    if mr:
        d = int(mr.group(1))
        if d > 96:
            return None
        return Dimension(shape=Shape.ROUND, width_in=d, raw_text=mr.group(0).strip(), center=center)
    m = _RECT.search(text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w > 96 or h > 96:
            return None
        return Dimension(shape=Shape.RECT, width_in=w, height_in=h, raw_text=m.group(0).strip(), center=center)
    return None


def extract_dim_labels(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for span in line["spans"]:
                bb = span["bbox"]
                c = Point(x=(bb[0] + bb[2]) / 2, y=(bb[1] + bb[3]) / 2)
                d = parse_dim(span["text"], c)
                if d:
                    out.append(d)
    return out


def _run_center(run):
    mid = run.segments[len(run.segments) // 2]
    return Point(x=(mid.p1.x + mid.p2.x) / 2, y=(mid.p1.y + mid.p2.y) / 2)


def match_dims_to_runs(runs, dims, radius_pts):
    """Label-driven association: each dimension label is one real duct. Attach
    each label to its nearest run (closest label wins per run). Runs that no label
    claims are left undimensioned and are excluded from the takeoff/BoQ."""
    best_for_run = {}   # run_index -> (distance, dim)
    for d in dims:
        if not d.center:
            continue
        bi, bd = None, radius_pts
        for idx, run in enumerate(runs):
            rc = _run_center(run)
            dist = math.hypot(d.center.x - rc.x, d.center.y - rc.y)
            if dist < bd:
                bi, bd = idx, dist
        if bi is not None and (bi not in best_for_run or bd < best_for_run[bi][0]):
            best_for_run[bi] = (bd, d)
    for idx, run in enumerate(runs):
        if idx in best_for_run:
            dist, d = best_for_run[idx]
            run.dimension = d
            run.reasons.append(f"dim {d.raw_text} matched at {round(dist)}pt")
        else:
            run.confidence = min(run.confidence, 0.5)
            run.reasons.append("no dimension label matched within radius")
    return runs
