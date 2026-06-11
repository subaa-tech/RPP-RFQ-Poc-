from src.ductquote.loader import open_pdf
from src.ductquote.classify import classify_pages


def test_classify_segregates_m_sheet(synthetic_pdf):
    pages = classify_pages(open_pdf(synthetic_pdf))
    m = [p for p in pages if p.is_mechanical]
    assert len(m) == 1 and m[0].sheet_label == "M-101"
    a = [p for p in pages if p.sheet_label == "A-201"][0]
    assert a.is_mechanical is False
