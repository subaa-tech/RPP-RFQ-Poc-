from src.ductquote.models import DuctRun, DuctSegment, Point, FittingType
from src.ductquote.fittings import detect_fittings


def _run(rid, x1, y1, x2, y2):
    return DuctRun(id=rid, page_index=0,
                   segments=[DuctSegment(p1=Point(x=x1, y=y1), p2=Point(x=x2, y=y2),
                                         length_pts=((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)],
                   length_ft=1.0)


def test_detect_90_elbow():
    r1 = _run("R1", 0, 0, 100, 0)
    r2 = _run("R2", 100, 0, 100, 100)
    f = detect_fittings([r1, r2])
    assert any(x.type == FittingType.ELBOW_90 for x in f)


def test_detect_tee():
    r1 = _run("R1", 0, 0, 200, 0)
    r2 = _run("R2", 200, 0, 400, 0)
    r3 = _run("R3", 200, 0, 200, 120)
    f = detect_fittings([r1, r2, r3])
    assert any(x.type == FittingType.TEE for x in f)
