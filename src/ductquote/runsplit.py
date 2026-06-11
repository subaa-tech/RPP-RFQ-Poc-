"""Split a duct run where its size changes along its length.

A long straight run can carry two different size labels (e.g. 12x10 then 14x12).
This pass projects every alongside label onto the run's axis, groups consecutive
same-size labels, splits at the midpoint between size groups, and apportions the
run's length to each sub-run. Geometry is clipped per interval for annotation.
Runs with a single size are returned unchanged, so primary assignment/recall is preserved.
"""
import math
from .models import DuctRun, DuctSegment, Point


def _run_axis(run):
    pts = []
    for s in run.segments:
        pts += [(s.p1.x, s.p1.y), (s.p2.x, s.p2.y)]
    # principal axis = the farthest-apart endpoint pair
    bi, bj, bd = 0, 0, -1.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2
            if d > bd:
                bi, bj, bd = i, j, d
    A, B = pts[bi], pts[bj]
    L = math.hypot(B[0] - A[0], B[1] - A[1]) or 1e-9
    u = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
    return A, u, L


def _t(p, A, u):
    return (p[0] - A[0]) * u[0] + (p[1] - A[1]) * u[1]


def _perp(p, A, u):
    return abs((p[0] - A[0]) * u[1] - (p[1] - A[1]) * u[0])


def _sizekey(d):
    return (int(d.width_in or 0), int(d.height_in) if d.height_in else None, d.shape)


def _clip_segments(segments, A, u, t_lo, t_hi):
    out = []
    for s in segments:
        t1, t2 = _t((s.p1.x, s.p1.y), A, u), _t((s.p2.x, s.p2.y), A, u)
        if t1 == t2:
            continue
        a, b = max(min(t1, t2), t_lo), min(max(t1, t2), t_hi)
        if b <= a:
            continue
        fa, fb = (a - t1) / (t2 - t1), (b - t1) / (t2 - t1)
        fa, fb = max(0.0, min(1.0, fa)), max(0.0, min(1.0, fb))
        pa = Point(x=s.p1.x + (s.p2.x - s.p1.x) * fa, y=s.p1.y + (s.p2.y - s.p1.y) * fa)
        pb = Point(x=s.p1.x + (s.p2.x - s.p1.x) * fb, y=s.p1.y + (s.p2.y - s.p1.y) * fb)
        out.append(DuctSegment(p1=pa, p2=pb, length_pts=math.hypot(pb.x - pa.x, pb.y - pa.y)))
    if not out:   # synthesize a centerline stub so the interval still draws
        pa = Point(x=A[0] + u[0] * t_lo, y=A[1] + u[1] * t_lo)
        pb = Point(x=A[0] + u[0] * t_hi, y=A[1] + u[1] * t_hi)
        out.append(DuctSegment(p1=pa, p2=pb, length_pts=math.hypot(pb.x - pa.x, pb.y - pa.y)))
    return out


def split_ducts_by_size(ducts, dims, perp_radius=80.0, end_margin=50.0):
    out = []
    for run in ducts:
        A, u, L = _run_axis(run)
        cand = []
        for d in dims:
            if not d.center:
                continue
            c = (d.center.x, d.center.y)
            t = _t(c, A, u)
            if _perp(c, A, u) <= perp_radius and -end_margin <= t <= L + end_margin:
                cand.append((max(0.0, min(L, t)), d))
        if len(cand) <= 1:
            out.append(run)
            continue
        cand.sort(key=lambda x: x[0])
        groups = []   # [sizekey, dim, [t,...]]
        for t, d in cand:
            key = _sizekey(d)
            if groups and groups[-1][0] == key:
                groups[-1][2].append(t)
            else:
                groups.append([key, d, [t]])
        if len(groups) <= 1:
            out.append(run)
            continue
        bounds = [0.0]
        for i in range(len(groups) - 1):
            bounds.append((groups[i][2][-1] + groups[i + 1][2][0]) / 2)
        bounds.append(L)
        for gi, (key, d, _ts) in enumerate(groups):
            lo, hi = bounds[gi], bounds[gi + 1]
            frac = (hi - lo) / L if L else 0.0
            seglen = round(run.length_ft * frac, 2)
            out.append(DuctRun(
                id=f"{run.id}.{gi + 1}", page_index=run.page_index,
                segments=_clip_segments(run.segments, A, u, lo, hi),
                length_ft=seglen, dimension=d, system=run.system, confidence=run.confidence,
                reasons=run.reasons + [f"size-split: {key[0]}x{key[1]} over {seglen}ft of the run"],
            ))
    return out
