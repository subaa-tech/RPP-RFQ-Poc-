from src.ductquote.models import DuctRun, DuctSegment, Point
from src.ductquote.review import build_review_report


def test_review_lists_low_confidence():
    runs = [DuctRun(id="M-101-R5", page_index=0,
                    segments=[DuctSegment(p1=Point(x=0, y=0), p2=Point(x=1, y=0), length_pts=1)],
                    length_ft=0.1, confidence=0.4,
                    reasons=["no dimension found — flagged for human review"])]
    md = build_review_report(runs, cutoff=0.7)
    assert "M-101-R5" in md and "review" in md.lower()
