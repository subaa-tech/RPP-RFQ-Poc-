import math
from .models import DuctRun, DuctSegment, Scale


def _collinear(a: DuctSegment, b: DuctSegment, tol: float = 2.0) -> bool:
    ang_a = math.degrees(math.atan2(a.p2.y - a.p1.y, a.p2.x - a.p1.x)) % 180
    ang_b = math.degrees(math.atan2(b.p2.y - b.p1.y, b.p2.x - b.p1.x)) % 180
    if min(abs(ang_a - ang_b), 180 - abs(ang_a - ang_b)) > 5:
        return False
    return min(math.hypot(a.p2.x - b.p1.x, a.p2.y - b.p1.y),
               math.hypot(a.p1.x - b.p2.x, a.p1.y - b.p2.y)) <= tol


def build_runs(segments, scale: Scale, page_index: int, sheet_label: str):
    for s in segments:
        s.length_ft = s.length_pts * scale.points_to_feet
    runs = []
    used = set()
    for i, s in enumerate(segments):
        if i in used:
            continue
        group = [s]
        used.add(i)
        for j in range(i + 1, len(segments)):
            if j in used:
                continue
            if any(_collinear(g, segments[j]) for g in group):
                group.append(segments[j])
                used.add(j)
        total_ft = sum(g.length_ft for g in group)
        runs.append(DuctRun(
            id=f"{sheet_label}-R{len(runs) + 1}", page_index=page_index,
            segments=group, length_ft=round(total_ft, 2),
            reasons=[f"{len(group)} segment(s), {round(total_ft, 2)} ft @ scale {scale.points_to_feet:.4f} ft/pt"],
        ))
    return runs
