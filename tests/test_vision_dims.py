from src.ductquote.models import DuctRun, DuctSegment, Point
from src.ductquote.llm import NullClient
from src.ductquote.vision_dims import fill_missing_dims


def test_unmatched_run_flagged_when_no_llm():
    run = DuctRun(id="M-101-R1", page_index=0,
                  segments=[DuctSegment(p1=Point(x=0, y=0), p2=Point(x=10, y=0), length_pts=10)],
                  length_ft=1.0, confidence=0.5)
    out = fill_missing_dims(None, [run], client=NullClient())
    assert out[0].dimension is None and "review" in " ".join(out[0].reasons).lower()
