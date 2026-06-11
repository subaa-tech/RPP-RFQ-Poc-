from src.ductquote.loader import open_pdf
from src.ductquote.pagetype import page_type


def test_classify_vector(synthetic_pdf):
    assert page_type(open_pdf(synthetic_pdf)[0]) == "vector"


def test_classify_raster(raster_pdf):
    assert page_type(open_pdf(raster_pdf)[0]) == "raster"


def test_classify_shx(shx_pdf):
    assert page_type(open_pdf(shx_pdf)[0]) == "shx"
