"""Page-type triage (KT's first step): classify each page as vector / raster / SHX
so it can be routed to the right extractors.

- vector : real machine-readable text + vector drawings -> read everything programmatically
- raster : a large embedded image dominates, no real text -> needs CV (geometry) + OCR/vision (text)
- shx    : lots of vector geometry but text is stored as strokes (sparse/garbled get_text)
           -> geometry via get_drawings works; text needs OCR/vision
"""
import re
import fitz

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _is_garbled(text):
    t = text.strip()
    if len(t) < 50:
        return True
    return len(_CTRL.findall(text)) / max(1, len(text)) > 0.05


def _max_image_coverage(page):
    try:
        infos = page.get_image_info()
    except Exception:
        infos = []
    page_area = abs(page.rect.width * page.rect.height) or 1.0
    best = 0.0
    for im in infos:
        bb = im.get("bbox")
        if bb:
            r = fitz.Rect(bb)
            best = max(best, abs(r.width * r.height) / page_area)
    return best


def page_type(page) -> str:
    text = page.get_text()
    if not _is_garbled(text):
        return "vector"                 # good readable text -> vector (fast path, no get_drawings)
    cov = _max_image_coverage(page)
    if cov >= 0.5:
        return "raster"
    if len(page.get_drawings()) >= 50:
        return "shx"
    return "raster" if cov > 0.2 else "vector"
