"""Raster (flattened PNG/JPEG) duct geometry via OpenCV.

Renders the page to a grayscale image and detects line segments with a probabilistic
Hough transform, returning the SAME shape as geometry.extract_lines ((Point, Point, color))
in PDF points, so the rest of the pipeline (pair_walls, build_runs, scale) works unchanged.
"""
import math
import fitz
from .models import Point


def have_cv2():
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def extract_lines_raster(page, dpi=150, threshold=60, min_len_in=0.2, max_gap_px=4):
    if not have_cv2():
        return []
    import cv2
    import numpy as np

    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    edges = cv2.Canny(img, 50, 150, apertureSize=3)
    min_len_px = max(20, int(dpi * min_len_in))
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180, threshold=threshold,
                            minLineLength=min_len_px, maxLineGap=max_gap_px)
    s = 72.0 / dpi   # pixels -> PDF points
    out = []
    if lines is not None:
        for ln in lines:
            x1, y1, x2, y2 = (float(v) for v in ln[0])
            out.append((Point(x=x1 * s, y=y1 * s), Point(x=x2 * s, y=y2 * s), None))
    return out
