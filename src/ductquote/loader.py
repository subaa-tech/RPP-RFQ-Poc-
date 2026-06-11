import re
import fitz
from .models import Scale
from .config import load_settings

_SCALE_RE = re.compile(r'(\d+)\s*/\s*(\d+)\s*"\s*=\s*(\d+)\s*[\'’]\s*-\s*(\d+)\s*"')


def open_pdf(path: str) -> fitz.Document:
    return fitz.open(path)


def parse_scale(text: str) -> Scale:
    m = _SCALE_RE.search(text)
    if m:
        num, den, feet, inch = (int(g) for g in m.groups())
        paper_inches = num / den
        paper_points = paper_inches * 72.0
        real_feet = feet + inch / 12.0
        return Scale(raw=m.group(0), points_to_feet=real_feet / paper_points, source="parsed")
    return Scale(raw="", points_to_feet=load_settings()["scale"]["default_points_to_feet"], source="default")
