import re
import fitz
from .models import Scale
from .config import load_settings

_SCALE_RE = re.compile(r'(\d+)\s*/\s*(\d+)\s*"\s*=\s*(\d+)\s*[\'’]\s*-\s*(\d+)\s*"')

# Common architectural scales (X" on paper = 1'-0" real) -> feet per PDF point (72 pt/inch).
SCALE_CHOICES = {
    '1/16': 1.0 / (0.0625 * 72),
    '3/32': 1.0 / (0.09375 * 72),
    '1/8': 1.0 / (0.125 * 72),
    '3/16': 1.0 / (0.1875 * 72),
    '1/4': 1.0 / (0.25 * 72),
    '3/8': 1.0 / (0.375 * 72),
    '1/2': 1.0 / (0.5 * 72),
}


def points_to_feet_for(choice: str):
    """Map a user scale choice (e.g. '1/4') to feet-per-point. Returns None for 'auto'/unknown."""
    if not choice or choice == "auto":
        return None
    return SCALE_CHOICES.get(choice.strip().replace('"', ''))


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
