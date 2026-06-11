from src.ductquote.models import DuctRun, DuctSegment, Point, Dimension, Shape
from src.ductquote.runsplit import split_ducts_by_size


def _dim(w, h, x):
    return Dimension(shape=Shape.RECT, width_in=w, height_in=h, center=Point(x=x, y=5))


def test_split_run_at_size_boundary():
    seg = DuctSegment(p1=Point(x=0, y=0), p2=Point(x=180, y=0), length_pts=180)
    run = DuctRun(id="M-1-P1-R1", page_index=0, segments=[seg], length_ft=20.0,
                  dimension=_dim(14, 12, 140))
    dims = [_dim(12, 10, 40), _dim(14, 12, 140)]
    out = split_ducts_by_size([run], dims, perp_radius=40)
    assert len(out) == 2
    sizes = sorted((int(r.dimension.width_in), int(r.dimension.height_in)) for r in out)
    assert sizes == [(12, 10), (14, 12)]
    # boundary at (40+140)/2 = 90 -> each half = 10 ft
    assert all(abs(r.length_ft - 10.0) < 0.5 for r in out)
    assert abs(sum(r.length_ft for r in out) - 20.0) < 0.01


def test_single_size_unchanged():
    seg = DuctSegment(p1=Point(x=0, y=0), p2=Point(x=180, y=0), length_pts=180)
    run = DuctRun(id="M-1-P1-R1", page_index=0, segments=[seg], length_ft=20.0,
                  dimension=_dim(14, 12, 90))
    dims = [_dim(14, 12, 60), _dim(14, 12, 120)]   # same size twice -> no split
    out = split_ducts_by_size([run], dims, perp_radius=40)
    assert len(out) == 1 and out[0].id == "M-1-P1-R1"
