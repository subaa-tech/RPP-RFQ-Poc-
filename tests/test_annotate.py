import os
from src.ductquote.loader import open_pdf
from src.ductquote.annotate import annotate_page
from src.ductquote.models import DuctRun, DuctSegment, Point


def test_annotate_writes_png(synthetic_pdf, tmp_path):
    doc = open_pdf(synthetic_pdf)
    run = DuctRun(id="M-101-R1", page_index=0,
                  segments=[DuctSegment(p1=Point(x=100, y=209), p2=Point(x=190, y=209), length_pts=90)],
                  length_ft=10.0)
    out = annotate_page(doc, 0, [run], [], str(tmp_path / "a.png"))
    assert os.path.exists(out) and os.path.getsize(out) > 0
