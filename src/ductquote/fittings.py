import math
from .models import Fitting, FittingType
from .config import load_settings


def _endpoints(run):
    return run.segments[0].p1, run.segments[-1].p2


def _dir(a, b):
    return math.degrees(math.atan2(b.y - a.y, b.x - a.x)) % 360


def _angle_between(d1, d2):
    a = abs(d1 - d2) % 360
    return min(a, 360 - a)


def detect_fittings(runs):
    """Geometric junction detection: endpoint->endpoint = elbow (by angle),
    3+ incident = tee. Deduped by location+type."""
    S = load_settings()["fittings"]
    tol = S["junction_tol_pts"]
    out = []
    fid = 0
    pts = [(r, *_endpoints(r)) for r in runs]
    for i in range(len(pts)):
        ri, ai, bi = pts[i]
        for end_i in (ai, bi):
            incident = []
            for j in range(len(pts)):
                rj, aj, bj = pts[j]
                for end_j in (aj, bj):
                    if rj.id == ri.id and end_j is end_i:
                        continue
                    if math.hypot(end_i.x - end_j.x, end_i.y - end_j.y) <= tol:
                        far = bj if end_j is aj else aj
                        incident.append((rj.id, _dir(end_i, far)))
            if not incident:
                continue
            far_i = bi if end_i is ai else ai
            dir_i = _dir(end_i, far_i)
            ftype = FittingType.UNKNOWN
            if len(incident) == 1:
                ang = _angle_between(dir_i, incident[0][1])
                if S["elbow_90_range"][0] <= ang <= S["elbow_90_range"][1]:
                    ftype = FittingType.ELBOW_90
                elif S["elbow_45_range"][0] <= ang <= S["elbow_45_range"][1]:
                    ftype = FittingType.ELBOW_45
            elif len(incident) >= 2:
                ftype = FittingType.TEE
            if ftype != FittingType.UNKNOWN:
                fid += 1
                out.append(Fitting(
                    id=f"F{fid}", page_index=ri.page_index, type=ftype, location=end_i,
                    connected_run_ids=[ri.id] + [x[0] for x in incident],
                ))
    uniq = []
    seen = set()
    for f in out:
        key = (round(f.location.x), round(f.location.y), f.type)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq
