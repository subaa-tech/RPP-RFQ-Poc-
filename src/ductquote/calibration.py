"""Self-calibrate the drawing scale from the ducts themselves.

Text scale notation can be wrong or absent (e.g. duct plans enlarged to 1/4" while the
title block prints 1/8"). A SQUARE duct (W==H) is an unambiguous ruler: the perpendicular
gap between its two drawn walls equals W inches, so gap_pts / (W/12) = points-per-foot.
We take the median across all square ducts on the scaled floor plans.
"""
import math
import statistics
from .geometry import extract_lines, pair_walls
from .dimensions import extract_dim_labels


def derive_points_to_feet(doc, pages, S, fallback_feet_per_point, min_samples=6):
    """Measure the real scale (FEET per PDF point) from square ducts. For a WxW duct the
    wall gap = W inches, so feet_per_point = (W/12) / gap_pts. Returns
    (feet_per_point, n_samples, source). Only meant to OVERRIDE the text scale when it
    disagrees materially (the caller decides); otherwise the text scale is kept."""
    rfrac = S["match"]["drawing_right_frac"]
    bfrac = S["match"]["drawing_bottom_frac"]
    radius = 35.0   # square-duct label must sit right on the paired run
    samples = []
    for p in pages:
        page = doc[p.index]
        lines = extract_lines(page)
        dims = [d for d in extract_dim_labels(page)
                if d.center and d.center.x <= rfrac * page.rect.width
                and d.center.y <= bfrac * page.rect.height]
        squares = [(d.center, d.width_in) for d in dims
                   if d.width_in and d.height_in == d.width_in]
        if not squares:
            continue
        anchors = [d.center for d in dims if d.center]
        for seg in pair_walls(lines, anchors=anchors):
            if seg.wall_gap_pts <= 0:
                continue
            mx = (seg.p1.x + seg.p2.x) / 2
            my = (seg.p1.y + seg.p2.y) / 2
            best, bestd = None, radius
            for c, w in squares:
                d = math.hypot(mx - c.x, my - c.y)
                if d < bestd:
                    bestd, best = d, w
            if best:
                fpp = (best / 12.0) / seg.wall_gap_pts          # feet per point
                if 0.03 <= fpp <= 0.30:                          # ~1/2" .. ~1/16" scales
                    samples.append(fpp)
    if len(samples) >= min_samples:
        return statistics.median(samples), len(samples), "measured"
    return fallback_feet_per_point, len(samples), "text"
