from src.ductquote.models import DuctSegment, Point, Scale
from src.ductquote.runs import build_runs


def test_length_ft_at_eighth_scale():
    seg = DuctSegment(p1=Point(x=0, y=0), p2=Point(x=90, y=0), length_pts=90)
    runs = build_runs([seg], Scale(raw="", points_to_feet=1 / 9, source="default"),
                      page_index=0, sheet_label="M-101")
    assert round(runs[0].length_ft, 2) == 10.0
    assert runs[0].id == "M-101-P1-R1"
