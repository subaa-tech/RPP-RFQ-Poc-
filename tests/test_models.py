from src.ductquote.models import Dimension, Shape


def test_dimension_defaults():
    d = Dimension(shape=Shape.RECT, width_in=12, height_in=18)
    assert d.confidence == 1.0 and d.source == "text"
