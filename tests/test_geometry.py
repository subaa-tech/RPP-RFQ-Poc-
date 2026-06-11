from src.ductquote.loader import open_pdf
from src.ductquote.geometry import extract_lines, pair_walls
from src.ductquote.models import Point


def test_extract_lines_keeps_blue_duct_lines(synthetic_pdf):
    page = open_pdf(synthetic_pdf)[0]
    lines = extract_lines(page)
    assert len(lines) >= 2


def test_pair_walls_makes_one_centerline():
    lines = [(Point(x=100, y=200), Point(x=190, y=200), (0, 0, 1)),
             (Point(x=100, y=218), Point(x=190, y=218), (0, 0, 1))]
    segs = pair_walls(lines)
    assert len(segs) == 1
    assert abs(segs[0].p1.y - 209) < 1
