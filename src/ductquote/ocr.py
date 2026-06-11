"""Dimension-label text for raster / SHX pages (where get_text fails).

Two pluggable backends, tried in order by the pipeline:
  1. Tesseract OCR  — deterministic, offline (needs the tesseract binary installed)
  2. LLM vision     — Gemini reads the rendered page (needs an API key / use_llm)
Both return [Dimension] with positions in PDF points, matching extract_dim_labels.
If neither is available the page yields no labels and is left for human review.
"""
import fitz
from .models import Point
from .dimensions import parse_dim


def tesseract_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_dim_labels_ocr(page, dpi=200):
    if not tesseract_available():
        return []
    import pytesseract
    from PIL import Image

    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    s = 72.0 / dpi
    out = []
    n = len(data["text"])
    for i in range(n):
        txt = data["text"][i]
        if not txt.strip():
            continue
        d = parse_dim(txt)
        if d:
            cx = (data["left"][i] + data["width"][i] / 2.0) * s
            cy = (data["top"][i] + data["height"][i] / 2.0) * s
            d.center = Point(x=cx, y=cy)
            d.source = "ocr"
            out.append(d)
    return out


def extract_dim_labels_vision(doc, page_index, client):
    if client is None:
        return []
    try:
        page = doc[page_index]
        W, H = page.rect.width, page.rect.height
        png = page.get_pixmap(dpi=150).tobytes("png")
        res = client.complete_json(
            "Read every HVAC duct size label on this plan (rectangular WxH in inches, or "
            'round diameter). Return JSON {"labels":[{"text":"14x12","x_frac":0.31,"y_frac":0.52}]} '
            "where x_frac/y_frac are the label centre as fractions of width/height.",
            images=[png],
        )
        out = []
        for lab in (res.get("labels") or []):
            d = parse_dim(str(lab.get("text", "")))
            if d:
                d.center = Point(x=float(lab.get("x_frac", 0.5)) * W,
                                 y=float(lab.get("y_frac", 0.5)) * H)
                d.source = "vision"
                out.append(d)
        return out
    except Exception:
        return []
