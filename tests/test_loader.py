from src.ductquote.loader import open_pdf, parse_scale


def test_parse_scale_eighth():
    s = parse_scale('FLOOR PLAN  1/8" = 1\'-0"  NORTH')
    assert round(s.points_to_feet, 4) == 0.1111 and s.source == "parsed"


def test_parse_scale_quarter():
    s = parse_scale('SCALE: 1/4" = 1\'-0"')
    assert round(s.points_to_feet, 5) == round(1 / 18, 5)


def test_parse_scale_default_when_absent():
    s = parse_scale("no scale here")
    assert s.source == "default"


def test_open_pdf(synthetic_pdf):
    doc = open_pdf(synthetic_pdf)
    assert doc.page_count == 2
