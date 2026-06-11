from src.ductquote.dimensions import parse_dim
from src.ductquote.models import Shape


def test_parse_rect():
    d = parse_dim('12x22')
    assert d.shape == Shape.RECT and d.width_in == 12 and d.height_in == 22


def test_parse_rect_inches():
    d = parse_dim('12"x22"')
    assert d.width_in == 12 and d.height_in == 22


def test_parse_round():
    d = parse_dim('14"Ø')
    assert d.shape == Shape.ROUND and d.width_in == 14 and d.height_in is None


def test_reject_oversize():
    assert parse_dim('120x200') is None


def test_scale_text_not_a_dimension():
    # "1/8" must NOT be read as a 1x8 duct
    assert parse_dim('1/8" = 1\'-0"') is None
