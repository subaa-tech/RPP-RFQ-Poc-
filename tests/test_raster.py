import pytest
from src.ductquote.loader import open_pdf
from src.ductquote.raster import extract_lines_raster, have_cv2
from src.ductquote.geometry import pair_walls
from src.ductquote.ocr import extract_dim_labels_ocr, tesseract_available


def test_raster_line_detection(raster_pdf):
    if not have_cv2():
        pytest.skip("opencv not installed")
    lines = extract_lines_raster(open_pdf(raster_pdf)[0])
    assert len(lines) >= 2          # the two horizontal duct walls recovered from the image
    # those parallel walls should pair into at least one centerline
    assert len(pair_walls(lines)) >= 1


def test_ocr_graceful_without_tesseract(raster_pdf):
    # With no tesseract binary this returns [] rather than raising.
    out = extract_dim_labels_ocr(open_pdf(raster_pdf)[0])
    if not tesseract_available():
        assert out == []
