from src.ductquote.loader import points_to_feet_for


def test_eighth_inch_scale():
    assert round(points_to_feet_for("1/8"), 4) == round(1 / 9, 4)


def test_quarter_inch_scale():
    assert round(points_to_feet_for("1/4"), 4) == round(1 / 18, 4)


def test_auto_returns_none():
    assert points_to_feet_for("auto") is None
    assert points_to_feet_for("") is None
