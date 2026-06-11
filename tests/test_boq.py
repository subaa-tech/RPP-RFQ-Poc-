from src.ductquote.models import DuctRun, DuctSegment, Point, Dimension, Shape
from src.ductquote.boq import build_boq


def test_boq_line_item_basic():
    run = DuctRun(id="M-101-R1", page_index=0,
                  segments=[DuctSegment(p1=Point(x=0, y=0), p2=Point(x=90, y=0), length_pts=90)],
                  length_ft=50.0,
                  dimension=Dimension(shape=Shape.RECT, width_in=24, height_in=12), confidence=1.0)
    items, thumb = build_boq([run])
    assert items[0].width_in == 24 and items[0].height_in == 12 and items[0].length_ft == 50.0
    assert thumb["clamps"] >= 1 and thumb["bolts"] == thumb["clamps"] * 4
