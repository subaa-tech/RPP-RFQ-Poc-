import re
import fitz
from .models import PageInfo

_LABEL_RE = re.compile(r'\b([MASEPC])\s*[-\.]?\s*(\d{1,3}[A-Z]?)\b')
_DIM_RE = re.compile(r'\b\d{1,2}\s*["”]?\s*[x×X]\s*\d{1,2}\b')


def _title_block_text(page: fitz.Page) -> str:
    r = page.rect
    quad = fitz.Rect(r.x0 + r.width * 0.55, r.y0 + r.height * 0.75, r.x1, r.y1)
    return page.get_textbox(quad)


def _largest_label(page: fitz.Page):
    best = None
    best_size = 0.0
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for span in line["spans"]:
                m = _LABEL_RE.search(span["text"])
                if m and span["size"] > best_size:
                    best, best_size = m, span["size"]
    return best


def classify_pages(doc: fitz.Document) -> list[PageInfo]:
    out = []
    for i, page in enumerate(doc):
        full = page.get_text()
        label_m = _largest_label(page)
        label = f"{label_m.group(1)}-{label_m.group(2)}" if label_m else None
        prefix = label_m.group(1) if label_m else None
        reasons = []
        score = 0.0
        if prefix == "M":
            score += 0.5
            reasons.append("M-prefix sheet label")
        if "PLAN" in full.upper():
            score += 0.3
            reasons.append("PLAN keyword")
        if '1/8"' in full or "= 1'-0" in full:
            score += 0.1
            reasons.append("scale present")
        dim_hits = len(_DIM_RE.findall(full))
        draws = len(page.get_drawings())
        if dim_hits >= 1 and draws >= 50:
            score += 0.2
            reasons.append(f"geometry: {dim_hits} dim labels, {draws} draws")
        is_mech = prefix == "M" and score >= 0.5
        out.append(PageInfo(
            index=i, sheet_label=label, title=_title_block_text(page).strip()[:60],
            is_mechanical=is_mech, score=min(score, 1.0), reasons=reasons,
        ))
    return out
