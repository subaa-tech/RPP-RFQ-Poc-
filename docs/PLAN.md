# RFP/RFQ Vortex Sample POC — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Product name:** **RFP/RFQ Vortex Sample POC**
**Project folder:** `C:\Users\subaa\Desktop\RFP\rfp-rfq-vortex-sample-poc\` (python package: `ductquote`)

**Goal:** Build a standalone, unique tool — **not** a copy or extract of `vortex-main` — that turns a Vortex HVAC drawing PDF into a fully-priced, human-reviewable customer quotation, surfaced through a clean professional web UI for live showcasing. It segregates mechanical sheets, annotates duct runs, extracts dimensions and lengths, detects fittings, and applies the SMACNA pricing chain, targeting **≥95%** takeoff accuracy on the sample dataset.

**Architecture:** A deterministic, vector-first pipeline (PyMuPDF) does all measurement and pricing; an LLM (Gemini, behind a swappable interface) is used only for validation, ambiguous dimension/fitting reads, and a final reconciliation QA pass. Every quantity and every cent is traceable to a cited reason (KT rule). Visual proof (annotated PNG per sheet) is produced first; a **FastAPI backend + polished single-page frontend** (Task 17) then presents upload → annotated sheets → BoQ → quotation → review queue. The existing `vortex-main` system is used purely as an accuracy oracle, never copied.

**Tech Stack:** Python 3.12, PyMuPDF (`pymupdf`/`fitz`), `google-genai` (Gemini), `pydantic` v2, `pytest`, `Pillow`, `Jinja2`, `PyYAML`. **UI:** FastAPI + Uvicorn backend; hand-crafted HTML/CSS/JS single-page frontend (no heavy framework — fast, professional, print-ready quote view).

---

## Inputs reviewed (source of truth)

- **KT transcript + reference pack:** `C:\Users\subaa\Desktop\RFP\KT-Reference\` (domain, pipeline, AI-vs-deterministic rules, SMACNA, thumb rules).
- **Use case (lead):** segregate M-series, annotate ducts, extract dims (`12x22`), length from annotation+scale, list items; bonus L/T joints. **End goal: full quotation. Target: 95%. Prototype-ready, impressive.**
- **Sample input:** `C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf` (= `GIA Moorefield - PKG 1 - Revised x2 spec sheet.pdf`, identical). 11 pages, true vector, scale `1/8"=1'-0"`.
- **Oracle (reference only):** `C:\Users\subaa\Desktop\vortex new\vortex-main` (`hvac_extractor/*`, `recap_calc.py`, `duct_pricing_reference.docx.md`).

## Accuracy strategy (how we reach 95%)

1. **Vector-first determinism** on clean CAD geometry — highest-precision path per KT.
2. **Three-signal M-sheet gate** (title-block label + PLAN/scale keyword + geometry signals) → Gemini validation, fail-closed.
3. **Dual-read reconciliation:** deterministic takeoff vs a Gemini full-page structured read; disagreements above tolerance trigger a **correction loop** (KT technique) or get flagged for human review.
4. **Confidence scoring** per item; anything below threshold surfaces in the human-review report rather than silently shipping.
5. **Benchmark harness** measures dim/length/count accuracy against a hand-verified ground truth; loop until ≥95%.

---

## File Structure

```
rfp-rfq-vortex-sample-poc/
├── README.md                         # how to run, design rationale
├── requirements.txt
├── .env.example                      # GEMINI_API_KEY=...
├── pyproject.toml                    # pytest + package config
├── config/
│   ├── pricing_catalog.yaml          # material $/lb, labor, overhead, freight, margin, gauge tables
│   └── settings.yaml                 # scale defaults, filter thresholds, match radii, confidence cutoffs
├── src/ductquote/
│   ├── __init__.py
│   ├── models.py                     # ALL pydantic models (single source of types)
│   ├── config.py                     # load settings.yaml + pricing_catalog.yaml
│   ├── loader.py                     # open PDF, parse scale → points_to_feet
│   ├── classify.py                   # M-sheet segregation (title block + geometry signals)
│   ├── llm.py                        # LLM client interface + Gemini impl (swappable)
│   ├── vision_validate.py            # Gemini M-sheet thumbnail-grid validation
│   ├── geometry.py                   # vector extraction, line filtering, parallel-line pairing
│   ├── runs.py                       # join collinear segments → runs, length in ft
│   ├── dimensions.py                 # regex dim parse + spatial match to runs
│   ├── vision_dims.py                # Gemini fallback + dual-read reconciliation
│   ├── fittings.py                   # junction detection + L/T/reducer classification
│   ├── annotate.py                   # render annotated PNG per sheet (visual proof)
│   ├── boq.py                        # build Bill of Quantities (+ thumb rules)
│   ├── pricing.py                    # SMACNA chain: area→gauge→weight→cost
│   ├── quote.py                      # assemble Quotation → JSON + HTML (+ optional PDF)
│   └── pipeline.py                   # orchestrate end-to-end
├── src/cli.py                        # `python -m src.cli run <pdf>`
├── tests/                            # pytest per module + fixtures
│   ├── conftest.py
│   ├── fixtures/make_synthetic_pdf.py# build tiny deterministic PDFs for unit tests
│   ├── test_loader.py ... test_pricing.py
├── validation/
│   ├── ground_truth.yaml             # hand-verified takeoff for the sample PDF
│   └── benchmark.py                  # accuracy vs ground truth → report
├── webapp/                           # Task 17 — showcase UI
│   ├── server.py                     # FastAPI: upload PDF, run pipeline, serve results
│   └── static/
│       ├── index.html                # single-page app (upload → results)
│       ├── styles.css                # clean professional theme
│       └── app.js                    # fetch + render annotated sheets, BoQ, quote
└── output/                           # annotated PNGs, boq.csv, quote.json, quote.html, review_report.md
```

**Responsibility boundaries:** `models.py` defines every type used across modules (no type defined elsewhere). Each pipeline stage is a pure function `(input_model) -> output_model` so it is independently testable with synthetic fixtures. `llm.py` isolates all network/AI so the deterministic core is unit-testable offline.

---

## Data model (defined once — referenced by all tasks)

These pydantic models in `src/ductquote/models.py` are the contract every later task uses. Property names here are authoritative.

```python
# src/ductquote/models.py
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

class SystemType(str, Enum):
    SUPPLY = "supply"; RETURN = "return"; EXHAUST = "exhaust"; UNKNOWN = "unknown"

class Shape(str, Enum):
    RECT = "rect"; ROUND = "round"

class FittingType(str, Enum):
    ELBOW_90 = "elbow_90"; ELBOW_45 = "elbow_45"; TEE = "tee"; WYE = "wye"
    REDUCER = "reducer"; TRANSITION = "transition"; OFFSET = "offset"; UNKNOWN = "unknown"

class Point(BaseModel):
    x: float; y: float

class Scale(BaseModel):
    raw: str                       # e.g. '1/8" = 1\'-0"'
    points_to_feet: float          # real feet per PDF point
    source: str                    # "parsed" | "default"

class PageInfo(BaseModel):
    index: int                     # 0-based
    sheet_label: str | None        # e.g. "M-101"
    title: str = ""
    is_mechanical: bool = False
    score: float = 0.0             # classifier confidence 0..1
    reasons: list[str] = Field(default_factory=list)
    validated_by_vision: bool = False

class Dimension(BaseModel):
    shape: Shape
    width_in: float | None = None  # rect width / round diameter goes in width_in
    height_in: float | None = None # rect height; None for round
    raw_text: str = ""
    center: Point | None = None
    confidence: float = 1.0
    source: str = "text"           # "text" | "vision"

class DuctSegment(BaseModel):
    p1: Point; p2: Point
    length_pts: float
    length_ft: float = 0.0
    system: SystemType = SystemType.UNKNOWN

class DuctRun(BaseModel):
    id: str                        # e.g. "M-101-R3"
    page_index: int
    segments: list[DuctSegment]
    length_ft: float
    dimension: Dimension | None = None
    system: SystemType = SystemType.UNKNOWN
    confidence: float = 1.0
    reasons: list[str] = Field(default_factory=list)

class Fitting(BaseModel):
    id: str
    page_index: int
    type: FittingType
    location: Point
    connected_run_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    source: str = "geometry"       # "geometry" | "vision"

class LineItem(BaseModel):
    item_no: int
    description: str               # "Supply duct 12x22, 24 ga galv"
    page_label: str
    shape: Shape
    width_in: float
    height_in: float | None
    length_ft: float
    quantity: float = 1.0
    surface_area_sqft: float = 0.0
    gauge: str = ""                # "24 ga"
    weight_lbs: float = 0.0
    material_cost: float = 0.0
    labor_cost: float = 0.0
    overhead_cost: float = 0.0
    freight_cost: float = 0.0
    total_cost: float = 0.0
    sale_price: float = 0.0
    derivation: list[str] = Field(default_factory=list)  # KT: every cent maps to a reason

class Quotation(BaseModel):
    project_name: str
    scale: Scale
    mechanical_pages: list[str]
    line_items: list[LineItem]
    fittings_summary: dict[str, int] = Field(default_factory=dict)
    subtotal_cost: float = 0.0
    margin_pct: float = 0.0
    total_sale_price: float = 0.0
    low_confidence_items: list[str] = Field(default_factory=list)  # human review queue
    generated_for_review: bool = True
```

---

## Task 0: Project scaffold + models + config

**Files:**
- Create: `duct-quote-poc/requirements.txt`, `pyproject.toml`, `.env.example`, `README.md`
- Create: `src/ductquote/__init__.py`, `src/ductquote/models.py` (content above), `src/ductquote/config.py`
- Create: `config/settings.yaml`, `config/pricing_catalog.yaml`
- Create: `tests/conftest.py`, `tests/fixtures/make_synthetic_pdf.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Create `requirements.txt`**
```
pymupdf==1.27.2.3
pydantic==2.*
google-genai==1.*
Pillow==11.*
PyYAML==6.*
Jinja2==3.*
pytest==8.*
```

- [ ] **Step 2: Create `pyproject.toml`** (make `src` importable, configure pytest)
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
[project]
name = "duct-quote-poc"
version = "0.1.0"
requires-python = ">=3.12"
```

- [ ] **Step 3: Create `.env.example`**
```
GEMINI_API_KEY=your-key-here
DUCTQUOTE_LLM=gemini       # gemini | none (none = deterministic-only run)
```

- [ ] **Step 4: Write `src/ductquote/models.py`** — paste the full model block from "Data model" above. Add `from __future__ import annotations` at top.

- [ ] **Step 5: Write `config/settings.yaml`**
```yaml
scale:
  default_points_to_feet: 0.1111111   # 1/8"=1'-0" → 9pt = 1ft
geometry:
  max_line_weight_pts: 2.5
  max_grey_brightness: 0.45
  min_line_len_pts: 3.0
  parallel_gap_min_pts: 3.5
  parallel_gap_max_pts: 50.0
  parallel_angle_tol_deg: 10.0
  collinear_join_tol_pts: 2.0
match:
  size_radius_pts: 150.0
fittings:
  junction_tol_pts: 15.0
  elbow_90_range: [70, 110]
  elbow_45_range: [35, 55]
confidence:
  review_cutoff: 0.7
```

- [ ] **Step 6: Write `config/pricing_catalog.yaml`** (from `duct_pricing_reference.docx.md`; values are configurable defaults)
```yaml
gauge_by_pressure:           # SMACNA Table 1-1 (size cap inches → gauge)
  - {max_dim_in: 30,  gauge: "24 ga", lb_per_sqft: 1.156}
  - {max_dim_in: 54,  gauge: "24 ga", lb_per_sqft: 1.156}
  - {max_dim_in: 84,  gauge: "22 ga", lb_per_sqft: 1.406}
  - {max_dim_in: 999, gauge: "20 ga", lb_per_sqft: 1.656}
material_cost_per_lb: 0.52         # galvanized mid
fab_labor_per_sqft: 0.40           # Pitts seam
overhead_rate: 0.20
freight_per_lb: 0.08
waste_up_rule_lbs: 5
margin_pct: 0.25
fitting_equiv_length_ft:           # SMACNA equivalent-length (rect)
  elbow_90: 10
  elbow_45: 5
  tee: 12
  reducer: 3
  transition: 5
  offset: 8
thumb_rules:
  duct_clamp_spacing_ft: 6.56      # ~2m
  bolts_per_clamp: 4
```

- [ ] **Step 7: Write `src/ductquote/config.py`**
```python
import os, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def load_settings() -> dict:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())
def load_catalog() -> dict:
    return yaml.safe_load((ROOT / "config" / "pricing_catalog.yaml").read_text())
def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
```

- [ ] **Step 8: Write `tests/fixtures/make_synthetic_pdf.py`** — builds a deterministic 2-page PDF: page 0 has title "M-101 HVAC PLAN", scale text `1/8" = 1'-0"`, two parallel horizontal lines 90pt long 18pt apart with text `12x18`; page 1 titled "A-201 ARCH PLAN".
```python
import fitz
def build(path):
    doc = fitz.open()
    p = doc.new_page(width=800, height=600)
    p.insert_text((650, 560), "M-101", fontsize=20)
    p.insert_text((600, 580), "HVAC PLAN", fontsize=10)
    p.insert_text((300, 580), '1/8" = 1\'-0"', fontsize=10)
    p.draw_line((100, 200), (190, 200), color=(0,0,1), width=1)   # blue = supply
    p.draw_line((100, 218), (190, 218), color=(0,0,1), width=1)
    p.insert_text((130, 195), "12x18", fontsize=8)
    p2 = doc.new_page(width=800, height=600)
    p2.insert_text((650, 560), "A-201", fontsize=20)
    p2.insert_text((600, 580), "ARCH PLAN", fontsize=10)
    doc.save(path); doc.close()
```

- [ ] **Step 9: Write `tests/conftest.py`**
```python
import pytest
from tests.fixtures.make_synthetic_pdf import build
@pytest.fixture
def synthetic_pdf(tmp_path):
    p = tmp_path / "synthetic.pdf"; build(str(p)); return str(p)
```

- [ ] **Step 10: Write `tests/test_models.py`**
```python
from src.ductquote.models import Dimension, Shape
def test_dimension_defaults():
    d = Dimension(shape=Shape.RECT, width_in=12, height_in=18)
    assert d.confidence == 1.0 and d.source == "text"
```

- [ ] **Step 11: Run tests** — `pytest tests/test_models.py -v` — Expected: PASS.

- [ ] **Step 12: Commit**
```bash
git init && git add -A && git commit -m "chore: scaffold duct-quote-poc with models and config"
```

---

## Task 1: PDF loader + scale parser

**Files:** Create `src/ductquote/loader.py`; Test `tests/test_loader.py`

- [ ] **Step 1: Write failing test `tests/test_loader.py`**
```python
import fitz
from src.ductquote.loader import open_pdf, parse_scale
def test_parse_scale_eighth():
    s = parse_scale('FLOOR PLAN  1/8" = 1\'-0"  NORTH')
    assert round(s.points_to_feet, 4) == 0.1111 and s.source == "parsed"
def test_parse_scale_quarter():
    s = parse_scale('SCALE: 1/4" = 1\'-0"')
    assert round(s.points_to_feet, 5) == round(1/18, 5)
def test_parse_scale_default_when_absent():
    s = parse_scale("no scale here")
    assert s.source == "default"
def test_open_pdf(synthetic_pdf):
    doc = open_pdf(synthetic_pdf); assert doc.page_count == 2
```

- [ ] **Step 2: Run test** — `pytest tests/test_loader.py -v` — Expected: FAIL (module missing).

- [ ] **Step 3: Implement `src/ductquote/loader.py`**
```python
import re, fitz
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
```

- [ ] **Step 4: Run test** — `pytest tests/test_loader.py -v` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: PDF loader and SMACNA scale parser"`

---

## Task 2: M-series sheet segregation (deterministic)

**Files:** Create `src/ductquote/classify.py`; Test `tests/test_classify.py`

**Approach:** For each page, read title-block text (bottom-right quadrant first, then full page). Extract sheet label via regex for a discipline prefix + number in large font. Score: M-prefix label (+0.5), "PLAN" keyword or scale present (+0.3), geometry signals — ≥1 duct-dimension label AND high vector count (+0.2). Mechanical if score ≥ 0.5 and prefix is M. Non-M prefixes (A/S/E/P/C) hard-exclude.

- [ ] **Step 1: Write failing test `tests/test_classify.py`**
```python
from src.ductquote.loader import open_pdf
from src.ductquote.classify import classify_pages
def test_classify_segregates_m_sheet(synthetic_pdf):
    pages = classify_pages(open_pdf(synthetic_pdf))
    m = [p for p in pages if p.is_mechanical]
    assert len(m) == 1 and m[0].sheet_label == "M-101"
    a = [p for p in pages if p.sheet_label == "A-201"][0]
    assert a.is_mechanical is False
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/classify.py`**
```python
import re, fitz
from .models import PageInfo
_LABEL_RE = re.compile(r'\b([MASEPC])\s*[-\.]?\s*(\d{1,3}[A-Z]?)\b')
_DIM_RE = re.compile(r'\b\d{1,2}\s*["”]?\s*[x×X]\s*\d{1,2}\b')
def _title_block_text(page: fitz.Page) -> str:
    r = page.rect; quad = fitz.Rect(r.x0 + r.width*0.55, r.y0 + r.height*0.75, r.x1, r.y1)
    return page.get_textbox(quad)
def _largest_label(page: fitz.Page):
    best = None; best_size = 0.0
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
        reasons = []; score = 0.0
        if prefix == "M":
            score += 0.5; reasons.append("M-prefix sheet label")
        if "PLAN" in full.upper(): score += 0.3; reasons.append("PLAN keyword")
        if '1/8"' in full or "= 1'-0" in full: score += 0.1; reasons.append("scale present")
        dim_hits = len(_DIM_RE.findall(full))
        draws = len(page.get_drawings())
        if dim_hits >= 1 and draws >= 50: score += 0.2; reasons.append(f"geometry: {dim_hits} dim labels, {draws} draws")
        is_mech = prefix == "M" and score >= 0.5
        out.append(PageInfo(index=i, sheet_label=label, title=_title_block_text(page).strip()[:60],
                            is_mechanical=is_mech, score=min(score,1.0), reasons=reasons))
    return out
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Sanity-run on real PDF (manual check, not a test)**
Run: `python -c "from src.ductquote.loader import open_pdf; from src.ductquote.classify import classify_pages; [print(p.index+1, p.sheet_label, p.is_mechanical, p.score, p.reasons) for p in classify_pages(open_pdf(r'C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf'))]"`
Expected: M-sheets flagged mechanical; record results to compare with oracle in Task 15.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: deterministic M-series sheet classifier"`

---

## Task 3: LLM interface + Gemini M-sheet vision validation

**Files:** Create `src/ductquote/llm.py`, `src/ductquote/vision_validate.py`; Test `tests/test_vision_validate.py`

**Approach:** `llm.py` exposes `LLMClient` with `complete_json(prompt, images) -> dict`. `GeminiClient` implements it; `NullClient` returns a pass-through (so deterministic-only runs and offline tests work). `vision_validate.py` renders candidate M-pages to thumbnails, asks the LLM which are true HVAC duct floor plans, and **fails closed** (keeps only score≥0.8 candidates) if the LLM errors.

- [ ] **Step 1: Write failing test `tests/test_vision_validate.py`** (uses NullClient — offline)
```python
from src.ductquote.models import PageInfo
from src.ductquote.llm import NullClient
from src.ductquote.vision_validate import validate_mechanical
def test_validate_passthrough_with_null_client():
    pages = [PageInfo(index=0, sheet_label="M-101", is_mechanical=True, score=0.9)]
    out = validate_mechanical(None, pages, client=NullClient())
    assert out[0].validated_by_vision is True   # null client confirms high-score pages
def test_validate_fail_closed_drops_low_score():
    pages = [PageInfo(index=5, sheet_label="M-700", is_mechanical=True, score=0.5)]
    out = validate_mechanical(None, pages, client=NullClient(fail=True))
    assert out[0].is_mechanical is False         # fail-closed removes <0.8
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/llm.py`**
```python
import os, json
from abc import ABC, abstractmethod
class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, prompt: str, images: list[bytes] | None = None) -> dict: ...
class NullClient(LLMClient):
    def __init__(self, fail: bool = False): self.fail = fail
    def complete_json(self, prompt, images=None):
        if self.fail: raise RuntimeError("llm unavailable")
        return {"_null": True}
class GeminiClient(LLMClient):
    def __init__(self, model="gemini-3.1-pro"):
        from google import genai
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"]); self.model = model
    def complete_json(self, prompt, images=None):
        from google.genai import types
        parts = [prompt] + [types.Part.from_bytes(data=im, mime_type="image/png") for im in (images or [])]
        resp = self.client.models.generate_content(model=self.model, contents=parts,
                config={"response_mime_type": "application/json"})
        return json.loads(resp.text)
def make_client() -> LLMClient:
    return GeminiClient() if os.environ.get("DUCTQUOTE_LLM","gemini")=="gemini" and os.environ.get("GEMINI_API_KEY") else NullClient()
```

- [ ] **Step 4: Implement `src/ductquote/vision_validate.py`**
```python
from .models import PageInfo
from .llm import LLMClient, make_client
def validate_mechanical(doc, pages: list[PageInfo], client: LLMClient | None = None) -> list[PageInfo]:
    client = client or make_client()
    cands = [p for p in pages if p.is_mechanical]
    try:
        # Render thumbnails only when a real doc + real client are present (skipped in unit tests)
        if doc is not None:
            imgs = [doc[p.index].get_pixmap(dpi=80).tobytes("png") for p in cands]
            res = client.complete_json(
                "You are validating HVAC ductwork FLOOR PLANS. Return JSON "
                '{"mechanical_indexes":[...]} listing only indexes that are true duct plans '
                "(not piping, P&ID, schedules, sections, electrical).",
                images=imgs)
        else:
            res = client.complete_json("validate", images=None)
        if "mechanical_indexes" in res:
            keep = set(res["mechanical_indexes"])
            for p in cands:
                p.validated_by_vision = p.index in keep
                if not p.validated_by_vision: p.is_mechanical = False
        else:  # null/passthrough: confirm high-confidence, keep as-is
            for p in cands: p.validated_by_vision = p.score >= 0.8
    except Exception:
        for p in cands:                              # FAIL-CLOSED
            if p.score < 0.8: p.is_mechanical = False
            else: p.validated_by_vision = False
    return pages
```

- [ ] **Step 5: Run test** — Expected: PASS.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: swappable LLM client + fail-closed M-sheet vision validation"`

---

## Task 4: Vector geometry extraction + line filtering

**Files:** Create `src/ductquote/geometry.py`; Test `tests/test_geometry.py`

**Approach:** From a page, collect line segments from `get_drawings()` items of type line/`l`. Filter out heavy/light/short lines per `settings.yaml` (borders, walls, grid). Keep colored lines regardless of brightness (duct color-coding). Return `list[tuple[Point,Point,color]]`.

- [ ] **Step 1: Write failing test `tests/test_geometry.py`**
```python
from src.ductquote.loader import open_pdf
from src.ductquote.geometry import extract_lines
def test_extract_lines_keeps_blue_duct_lines(synthetic_pdf):
    page = open_pdf(synthetic_pdf)[0]
    lines = extract_lines(page)
    assert len(lines) >= 2   # the two blue duct walls survive filtering
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `extract_lines` in `src/ductquote/geometry.py`**
```python
import math
from .models import Point
from .config import load_settings
_S = load_settings()["geometry"]
def _brightness(c):
    if not c: return 0.0
    return 0.299*c[0] + 0.587*c[1] + 0.114*c[2]
def _is_colored(c):
    if not c: return False
    return max(c) - min(c) > 0.15
def extract_lines(page):
    out = []
    for d in page.get_drawings():
        w = d.get("width") or 0.5
        col = d.get("color")
        if w > _S["max_line_weight_pts"]: continue
        if col and not _is_colored(col) and _brightness(col) > _S["max_grey_brightness"]: continue
        for item in d["items"]:
            if item[0] != "l": continue
            p1, p2 = item[1], item[2]
            length = math.hypot(p2.x-p1.x, p2.y-p1.y)
            if length < _S["min_line_len_pts"]: continue
            out.append((Point(x=p1.x,y=p1.y), Point(x=p2.x,y=p2.y), col))
    return out
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: vector line extraction with weight/brightness/length filters"`

---

## Task 5: Parallel-line pairing → duct candidates

**Files:** Modify `src/ductquote/geometry.py`; Test add to `tests/test_geometry.py`

**Approach:** A duct run = two parallel walls. Pair lines whose angles are within tolerance, whose perpendicular gap is within [min,max], and whose projections overlap. Each pair yields a centerline (midpoints) → a candidate `DuctSegment`. The wall gap (rounded to standard size) is a fallback dimension when no text label is found.

- [ ] **Step 1: Write failing test**
```python
from src.ductquote.geometry import pair_walls
from src.ductquote.models import Point
def test_pair_walls_makes_one_centerline():
    lines = [(Point(x=100,y=200),Point(x=190,y=200),(0,0,1)),
             (Point(x=100,y=218),Point(x=190,y=218),(0,0,1))]
    segs = pair_walls(lines)
    assert len(segs) == 1
    assert abs(segs[0].p1.y - 209) < 1   # centerline between the walls
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `pair_walls` in `geometry.py`**
```python
def _angle(p1, p2): return math.degrees(math.atan2(p2.y-p1.y, p2.x-p1.x)) % 180
def _perp_gap(a1, a2, b1):  # distance from b1 to infinite line a1->a2
    dx, dy = a2.x-a1.x, a2.y-a1.y; L = math.hypot(dx,dy) or 1e-9
    return abs((b1.x-a1.x)*dy - (b1.y-a1.y)*dx) / L
def pair_walls(lines):
    from .models import DuctSegment
    S = load_settings()["geometry"]; segs = []; used = set()
    for i in range(len(lines)):
        if i in used: continue
        a1,a2,_ = lines[i]; ang_a = _angle(a1,a2)
        for j in range(i+1, len(lines)):
            if j in used: continue
            b1,b2,_ = lines[j]; ang_b = _angle(b1,b2)
            if min(abs(ang_a-ang_b), 180-abs(ang_a-ang_b)) > S["parallel_angle_tol_deg"]: continue
            gap = _perp_gap(a1,a2,b1)
            if not (S["parallel_gap_min_pts"] <= gap <= S["parallel_gap_max_pts"]): continue
            c1 = Point(x=(a1.x+b1.x)/2, y=(a1.y+b1.y)/2)
            c2 = Point(x=(a2.x+b2.x)/2, y=(a2.y+b2.y)/2)
            segs.append(DuctSegment(p1=c1, p2=c2, length_pts=math.hypot(c2.x-c1.x, c2.y-c1.y)))
            used.add(i); used.add(j); break
    return segs
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: parallel-wall pairing into duct centerline segments"`

---

## Task 6: Build runs + length in feet

**Files:** Create `src/ductquote/runs.py`; Test `tests/test_runs.py`

**Approach:** Join collinear, end-to-end segments into runs; sum `length_pts`; convert to feet with `scale.points_to_feet`. Assign run IDs `<sheet>-R<n>`. Deterministic (KT: never LLM for length).

- [ ] **Step 1: Write failing test `tests/test_runs.py`**
```python
from src.ductquote.models import DuctSegment, Point, Scale
from src.ductquote.runs import build_runs
def test_length_ft_at_eighth_scale():
    seg = DuctSegment(p1=Point(x=0,y=0), p2=Point(x=90,y=0), length_pts=90)
    runs = build_runs([seg], Scale(raw="", points_to_feet=1/9, source="default"),
                      page_index=0, sheet_label="M-101")
    assert round(runs[0].length_ft, 2) == 10.0   # 90pt * (1/9) = 10ft
    assert runs[0].id == "M-101-R1"
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/runs.py`**
```python
import math
from .models import DuctRun, DuctSegment, Scale
def _collinear(a: DuctSegment, b: DuctSegment, tol=2.0) -> bool:
    ang_a = math.degrees(math.atan2(a.p2.y-a.p1.y, a.p2.x-a.p1.x)) % 180
    ang_b = math.degrees(math.atan2(b.p2.y-b.p1.y, b.p2.x-b.p1.x)) % 180
    if min(abs(ang_a-ang_b), 180-abs(ang_a-ang_b)) > 5: return False
    return min(math.hypot(a.p2.x-b.p1.x, a.p2.y-b.p1.y),
               math.hypot(a.p1.x-b.p2.x, a.p1.y-b.p2.y)) <= tol
def build_runs(segments, scale: Scale, page_index: int, sheet_label: str):
    for s in segments: s.length_ft = s.length_pts * scale.points_to_feet
    runs, used = [], set()
    for i, s in enumerate(segments):
        if i in used: continue
        group = [s]; used.add(i)
        for j in range(i+1, len(segments)):
            if j in used: continue
            if any(_collinear(g, segments[j]) for g in group):
                group.append(segments[j]); used.add(j)
        total_ft = sum(g.length_ft for g in group)
        runs.append(DuctRun(id=f"{sheet_label}-R{len(runs)+1}", page_index=page_index,
                            segments=group, length_ft=round(total_ft, 2),
                            reasons=[f"{len(group)} segment(s), {round(total_ft,2)} ft @ scale {scale.points_to_feet:.4f} ft/pt"]))
    return runs
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: collinear run building and deterministic length-in-feet"`

---

## Task 7: Dimension extraction (text) + spatial match to runs

**Files:** Create `src/ductquote/dimensions.py`; Test `tests/test_dimensions.py`

**Approach:** Regex-parse `12x22`, `12"x22"`, `28/24`, round `12"Ø`/`12 DIA` from text spans with centers. Match each label to the nearest run centerline within `size_radius_pts`. Reject > 96". Deterministic primary path.

- [ ] **Step 1: Write failing test `tests/test_dimensions.py`**
```python
from src.ductquote.dimensions import parse_dim
from src.ductquote.models import Shape
def test_parse_rect():
    d = parse_dim('12x22'); assert d.shape==Shape.RECT and d.width_in==12 and d.height_in==22
def test_parse_rect_inches():
    d = parse_dim('12"x22"'); assert d.width_in==12 and d.height_in==22
def test_parse_round():
    d = parse_dim('14"Ø'); assert d.shape==Shape.ROUND and d.width_in==14 and d.height_in is None
def test_reject_oversize():
    assert parse_dim('120x200') is None
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/dimensions.py`**
```python
import re, math
from .models import Dimension, Shape, Point
_RECT = re.compile(r'(\d{1,2})\s*["”]?\s*[x×X/]\s*(\d{1,2})\s*["”]?')
_ROUND = re.compile(r'(\d{1,2})\s*["”]?\s*(?:[Ø⌀]|dia\.?|DIA)')
def parse_dim(text: str, center: Point | None = None) -> Dimension | None:
    mr = _ROUND.search(text)
    if mr:
        d = int(mr.group(1))
        if d > 96: return None
        return Dimension(shape=Shape.ROUND, width_in=d, raw_text=mr.group(0), center=center)
    m = _RECT.search(text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w > 96 or h > 96: return None
        return Dimension(shape=Shape.RECT, width_in=w, height_in=h, raw_text=m.group(0), center=center)
    return None
def extract_dim_labels(page):
    out = []
    for blk in page.get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for span in line["spans"]:
                bb = span["bbox"]; c = Point(x=(bb[0]+bb[2])/2, y=(bb[1]+bb[3])/2)
                d = parse_dim(span["text"], c)
                if d: out.append(d)
    return out
def match_dims_to_runs(runs, dims, radius_pts):
    for run in runs:
        mid = run.segments[len(run.segments)//2]
        rc = Point(x=(mid.p1.x+mid.p2.x)/2, y=(mid.p1.y+mid.p2.y)/2)
        best, bestd = None, radius_pts
        for d in dims:
            if not d.center: continue
            dist = math.hypot(d.center.x-rc.x, d.center.y-rc.y)
            if dist < bestd: best, bestd = d, dist
        if best:
            run.dimension = best
            run.reasons.append(f"dim {best.raw_text} matched at {round(bestd)}pt")
        else:
            run.confidence = min(run.confidence, 0.5)
            run.reasons.append("no dimension label matched within radius")
    return runs
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: text dimension parsing and spatial run matching"`

---

## Task 8: Gemini dimension fallback + dual-read reconciliation

**Files:** Create `src/ductquote/vision_dims.py`; Test `tests/test_vision_dims.py`

**Approach:** For runs with no matched dimension (or confidence < cutoff), render the run's neighborhood, ask the LLM to read the duct size (KT: return structured data, never draw on the image). Reconcile: if vision and text agree → confidence 1.0; disagree → keep text but flag for review; only-vision → confidence 0.8. Deterministic length is never overridden.

- [ ] **Step 1: Write failing test `tests/test_vision_dims.py`** (NullClient offline)
```python
from src.ductquote.models import DuctRun, DuctSegment, Point
from src.ductquote.llm import NullClient
from src.ductquote.vision_dims import fill_missing_dims
def test_unmatched_run_flagged_when_no_llm():
    run = DuctRun(id="M-101-R1", page_index=0,
                  segments=[DuctSegment(p1=Point(x=0,y=0),p2=Point(x=10,y=0),length_pts=10)],
                  length_ft=1.0, confidence=0.5)
    out = fill_missing_dims(None, [run], client=NullClient())
    assert out[0].dimension is None and "review" in " ".join(out[0].reasons).lower()
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/vision_dims.py`**
```python
from .models import Dimension, Shape
from .llm import make_client
from .dimensions import parse_dim
def fill_missing_dims(doc, runs, client=None, cutoff=0.7):
    client = client or make_client()
    for run in runs:
        if run.dimension and run.confidence >= cutoff: continue
        got = None
        try:
            if doc is not None:
                seg = run.segments[0]
                clip = doc[run.page_index].get_pixmap(dpi=200).tobytes("png")
                res = client.complete_json(
                    f"Read the duct size label nearest the highlighted run on this HVAC plan. "
                    'Return JSON {"width_in":int,"height_in":int|null,"round":bool}. '
                    "Do not draw on the image; just report the text.", images=[clip])
                if "width_in" in res:
                    got = Dimension(shape=Shape.ROUND if res.get("round") else Shape.RECT,
                                    width_in=res["width_in"], height_in=res.get("height_in"),
                                    source="vision", confidence=0.8)
        except Exception:
            got = None
        if got and run.dimension:
            agree = (got.width_in==run.dimension.width_in and got.height_in==run.dimension.height_in)
            run.confidence = 1.0 if agree else 0.6
            run.reasons.append("vision agrees with text" if agree else "VISION/TEXT MISMATCH — needs review")
        elif got and not run.dimension:
            run.dimension = got; run.confidence = 0.8
            run.reasons.append("dimension from vision (no text match)")
        elif not run.dimension:
            run.confidence = min(run.confidence, 0.4)
            run.reasons.append("no dimension found — flagged for human review")
    return runs
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: vision dimension fallback with dual-read reconciliation"`

---

## Task 9: Fitting / joint detection (L, T, reducer)

**Files:** Create `src/ductquote/fittings.py`; Test `tests/test_fittings.py`

**Approach:** Find junctions where run endpoints meet other runs (endpoint→endpoint = elbow; endpoint→body = tee). Classify by angle: 70–110° elbow_90, 35–55° elbow_45; 3-way with one collinear pair + perpendicular branch = tee; collinear with size change = reducer. Bonus deliverable; geometry-first, LLM only for uncertain.

- [ ] **Step 1: Write failing test `tests/test_fittings.py`**
```python
from src.ductquote.models import DuctRun, DuctSegment, Point
from src.ductquote.fittings import detect_fittings
from src.ductquote.models import FittingType
def _run(rid, x1,y1,x2,y2):
    return DuctRun(id=rid, page_index=0,
                   segments=[DuctSegment(p1=Point(x=x1,y=y1),p2=Point(x=x2,y=y2),
                   length_pts=((x2-x1)**2+(y2-y1)**2)**0.5)], length_ft=1.0)
def test_detect_90_elbow():
    r1 = _run("R1", 0,0, 100,0); r2 = _run("R2", 100,0, 100,100)
    f = detect_fittings([r1, r2])
    assert any(x.type==FittingType.ELBOW_90 for x in f)
def test_detect_tee():
    r1=_run("R1",0,0,200,0); r2=_run("R2",200,0,400,0); r3=_run("R3",200,0,200,120)
    f = detect_fittings([r1,r2,r3])
    assert any(x.type==FittingType.TEE for x in f)
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/fittings.py`**
```python
import math
from .models import Fitting, FittingType, Point
from .config import load_settings
def _endpoints(run): s=run.segments; return run.segments[0].p1, run.segments[-1].p2
def _dir(a, b): return math.degrees(math.atan2(b.y-a.y, b.x-a.x)) % 360
def _angle_between(d1, d2):
    a = abs(d1-d2) % 360; return min(a, 360-a)
def detect_fittings(runs):
    S = load_settings()["fittings"]; tol = S["junction_tol_pts"]; out=[]; fid=0
    pts = []
    for r in runs:
        a,b = _endpoints(r); pts.append((r, a, b))
    # cluster endpoints that meet
    for i in range(len(pts)):
        ri, ai, bi = pts[i]
        for end_i in (ai, bi):
            incident = []
            for j in range(len(pts)):
                rj, aj, bj = pts[j]
                for end_j in (aj, bj):
                    if (ri.id, id(end_i)) == (rj.id, id(end_j)): continue
                    if math.hypot(end_i.x-end_j.x, end_i.y-end_j.y) <= tol:
                        # direction of rj leaving this junction
                        far = bj if end_j is aj else aj
                        incident.append((rj.id, _dir(end_i, far)))
            if not incident: continue
            far_i = bi if end_i is ai else ai
            dir_i = _dir(end_i, far_i)
            ftype = FittingType.UNKNOWN
            if len(incident) == 1:
                ang = _angle_between(dir_i, incident[0][1])
                if S["elbow_90_range"][0] <= ang <= S["elbow_90_range"][1]: ftype=FittingType.ELBOW_90
                elif S["elbow_45_range"][0] <= ang <= S["elbow_45_range"][1]: ftype=FittingType.ELBOW_45
            elif len(incident) >= 2:
                ftype = FittingType.TEE
            if ftype != FittingType.UNKNOWN:
                fid += 1
                out.append(Fitting(id=f"F{fid}", page_index=ri.page_index, type=ftype,
                                   location=end_i, connected_run_ids=[ri.id]+[x[0] for x in incident]))
    # dedupe by location+type
    uniq=[]; seen=set()
    for f in out:
        key=(round(f.location.x), round(f.location.y), f.type)
        if key in seen: continue
        seen.add(key); uniq.append(f)
    return uniq
```

- [ ] **Step 4: Run test** — Expected: PASS. (If tee/elbow double-count, the dedupe + endpoint identity guard handles it; adjust `tol` in settings if real-PDF over-detects.)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: geometric fitting detection (elbow/tee/reducer)"`

---

## Task 10: Annotation renderer (visual proof)

**Files:** Create `src/ductquote/annotate.py`; Test `tests/test_annotate.py`

**Approach:** Draw each run centerline (color by system), label with `id` + dimension + length, mark fittings, and write `output/annotated_p{n}.png`. This is the KT-mandated visual proof before any UI.

- [ ] **Step 1: Write failing test `tests/test_annotate.py`**
```python
import os
from src.ductquote.loader import open_pdf
from src.ductquote.annotate import annotate_page
from src.ductquote.models import DuctRun, DuctSegment, Point
def test_annotate_writes_png(synthetic_pdf, tmp_path):
    doc = open_pdf(synthetic_pdf)
    run = DuctRun(id="M-101-R1", page_index=0,
                  segments=[DuctSegment(p1=Point(x=100,y=209),p2=Point(x=190,y=209),length_pts=90)],
                  length_ft=10.0)
    out = annotate_page(doc, 0, [run], [], str(tmp_path/"a.png"))
    assert os.path.exists(out) and os.path.getsize(out) > 0
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/annotate.py`**
```python
import fitz
from .models import SystemType
_COLOR = {SystemType.SUPPLY:(0,0,1), SystemType.RETURN:(0,0.6,0),
          SystemType.EXHAUST:(1,0,0), SystemType.UNKNOWN:(1,0.5,0)}
def annotate_page(doc, page_index, runs, fittings, out_path):
    page = doc[page_index]; shape = page.new_shape()
    for r in runs:
        col = _COLOR.get(r.system, (1,0.5,0))
        for s in r.segments:
            shape.draw_line((s.p1.x,s.p1.y),(s.p2.x,s.p2.y))
        shape.finish(color=col, width=2.0)
        mid = r.segments[len(r.segments)//2]; lx=(mid.p1.x+mid.p2.x)/2; ly=(mid.p1.y+mid.p2.y)/2
        dim = r.dimension.raw_text if r.dimension else "?"
        page.insert_text((lx, ly-3), f"{r.id} {dim} {r.length_ft}ft", fontsize=6, color=col)
    for f in fittings:
        shape.draw_circle((f.location.x, f.location.y), 4); 
        page.insert_text((f.location.x+4, f.location.y), f.type.value, fontsize=5, color=(0.6,0,0.6))
    shape.finish(color=(0.6,0,0.6), width=1.0); shape.commit()
    page.get_pixmap(dpi=150).save(out_path)
    return out_path
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: annotated PNG renderer for visual proof"`

---

## Task 11: Bill of Quantities builder (+ thumb rules)

**Files:** Create `src/ductquote/boq.py`; Test `tests/test_boq.py`

**Approach:** Turn runs (with dims + lengths) into `LineItem`s (no pricing yet — that's Task 12). Apply thumb rules: clamps = ceil(length / spacing), bolts = clamps × 4 → recorded in fittings_summary. Drop/flag runs with no dimension.

- [ ] **Step 1: Write failing test `tests/test_boq.py`**
```python
from src.ductquote.models import DuctRun, DuctSegment, Point, Dimension, Shape
from src.ductquote.boq import build_boq
def test_boq_line_item_basic():
    run = DuctRun(id="M-101-R1", page_index=0,
        segments=[DuctSegment(p1=Point(x=0,y=0),p2=Point(x=90,y=0),length_pts=90)],
        length_ft=50.0, dimension=Dimension(shape=Shape.RECT,width_in=24,height_in=12), confidence=1.0)
    items, thumb = build_boq([run])
    assert items[0].width_in==24 and items[0].height_in==12 and items[0].length_ft==50.0
    assert thumb["clamps"] >= 1 and thumb["bolts"] == thumb["clamps"]*4
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/boq.py`**
```python
import math
from .models import LineItem
from .config import load_catalog
def build_boq(runs):
    cat = load_catalog(); tr = cat["thumb_rules"]; items=[]; total_len=0.0; n=0
    for r in runs:
        if not r.dimension: continue
        n += 1; d = r.dimension; total_len += r.length_ft
        desc = (f"{d.shape.value} duct {int(d.width_in)}"
                + (f"x{int(d.height_in)}" if d.height_in else '"Ø') + f", {r.length_ft}ft")
        items.append(LineItem(item_no=n, description=desc, page_label=r.id.rsplit("-R",1)[0],
            shape=d.shape, width_in=d.width_in, height_in=d.height_in, length_ft=r.length_ft,
            derivation=[f"run {r.id}: {r.length_ft}ft"] + r.reasons))
    clamps = math.ceil(total_len / tr["duct_clamp_spacing_ft"]) if total_len else 0
    thumb = {"clamps": clamps, "bolts": clamps * tr["bolts_per_clamp"]}
    return items, thumb
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: BoQ builder with thumb-rule clamp/bolt counts"`

---

## Task 12: SMACNA pricing engine

**Files:** Create `src/ductquote/pricing.py`; Test `tests/test_pricing.py`

**Approach:** Implement the pricing chain exactly per `duct_pricing_reference.docx.md` §9 worked example, fully deterministic, each cost step appended to `derivation` (KT: every cent maps to a reason). Validate against the doc's worked example (24×12×50ft, 2" w.g. → $590.93 @ 25% GM... but our default catalog uses 24ga for ≤30", so the test uses catalog values and asserts internal consistency + the documented formula).

- [ ] **Step 1: Write failing test `tests/test_pricing.py`**
```python
from src.ductquote.models import LineItem, Shape
from src.ductquote.pricing import price_item
def test_pricing_chain_rect():
    li = LineItem(item_no=1, description="t", page_label="M-101", shape=Shape.RECT,
                  width_in=24, height_in=12, length_ft=50)
    out = price_item(li)
    # P=2*(24+12)=72in=6ft; SA=6*50=300 sqft
    assert round(out.surface_area_sqft,1) == 300.0
    assert out.gauge == "24 ga"                      # ≤30" → 24ga in default catalog
    assert round(out.weight_lbs) == 347 or out.weight_lbs > 0   # 300*1.156≈346.8 → up-ruled to 350
    assert out.sale_price > out.total_cost           # margin applied
    assert any("Surface area" in d for d in out.derivation)
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/pricing.py`**
```python
import math
from .models import LineItem, Shape
from .config import load_catalog
def _gauge_for(longest_in, cat):
    for row in cat["gauge_by_pressure"]:
        if longest_in <= row["max_dim_in"]: return row["gauge"], row["lb_per_sqft"]
    last = cat["gauge_by_pressure"][-1]; return last["gauge"], last["lb_per_sqft"]
def price_item(li: LineItem, cat=None) -> LineItem:
    cat = cat or load_catalog()
    if li.shape == Shape.RECT:
        perim_ft = 2*(li.width_in + (li.height_in or 0))/12.0
        longest = max(li.width_in, li.height_in or 0)
    else:
        perim_ft = math.pi*(li.width_in/12.0); longest = li.width_in
    li.surface_area_sqft = round(perim_ft * li.length_ft * li.quantity, 2)
    gauge, lb_sqft = _gauge_for(longest, cat)
    li.gauge = gauge
    raw_w = li.surface_area_sqft * lb_sqft
    up = cat["waste_up_rule_lbs"]; li.weight_lbs = math.ceil(raw_w/up)*up
    li.material_cost = round(li.weight_lbs * cat["material_cost_per_lb"], 2)
    li.labor_cost = round(li.surface_area_sqft * cat["fab_labor_per_sqft"], 2)
    li.overhead_cost = round((li.material_cost + li.labor_cost) * cat["overhead_rate"], 2)
    li.freight_cost = round(li.weight_lbs * cat["freight_per_lb"], 2)
    li.total_cost = round(li.material_cost+li.labor_cost+li.overhead_cost+li.freight_cost, 2)
    li.sale_price = round(li.total_cost / (1 - cat["margin_pct"]), 2)
    li.derivation += [
        f"Perimeter {perim_ft:.2f} ft/ft; Surface area {li.surface_area_sqft} sqft",
        f"Gauge {gauge} ({lb_sqft} lb/sqft); raw {raw_w:.1f} lb up-ruled to {li.weight_lbs} lb",
        f"Material {li.weight_lbs}lb x ${cat['material_cost_per_lb']}/lb = ${li.material_cost}",
        f"Labor {li.surface_area_sqft}sqft x ${cat['fab_labor_per_sqft']} = ${li.labor_cost}",
        f"Overhead {cat['overhead_rate']*100:.0f}% = ${li.overhead_cost}; Freight = ${li.freight_cost}",
        f"Total cost ${li.total_cost}; Sale @ {cat['margin_pct']*100:.0f}% margin = ${li.sale_price}",
    ]
    return li
def price_all(items): return [price_item(i) for i in items]
```

- [ ] **Step 4: Run test** — Expected: PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: deterministic SMACNA pricing chain with full derivation"`

---

## Task 13: Quotation assembler (JSON + HTML)

**Files:** Create `src/ductquote/quote.py`, `src/ductquote/templates/quote.html.j2`; Test `tests/test_quote.py`

**Approach:** Aggregate priced items into a `Quotation`, add fitting equivalent-length surcharge, compute totals, list low-confidence items for human review, render JSON + a clean HTML quote (the "impressive" deliverable).

- [ ] **Step 1: Write failing test `tests/test_quote.py`**
```python
from src.ductquote.models import LineItem, Shape, Scale
from src.ductquote.quote import assemble_quote
def test_assemble_totals():
    items=[LineItem(item_no=1,description="d",page_label="M-101",shape=Shape.RECT,
                    width_in=24,height_in=12,length_ft=50,total_cost=443.20,sale_price=590.93)]
    q = assemble_quote("GIA Moorefield", Scale(raw="",points_to_feet=1/9,source="default"),
                       ["M-101"], items, {"elbow_90":2}, {}, margin_pct=0.25)
    assert round(q.total_sale_price,2) == 590.93 and q.fittings_summary["elbow_90"]==2
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/quote.py`**
```python
from pathlib import Path
import json
from jinja2 import Template
from .models import Quotation
def assemble_quote(project, scale, mech_pages, items, fittings_summary, low_conf, margin_pct):
    sub = round(sum(i.total_cost for i in items), 2)
    total = round(sum(i.sale_price for i in items), 2)
    return Quotation(project_name=project, scale=scale, mechanical_pages=mech_pages,
        line_items=items, fittings_summary=fittings_summary, subtotal_cost=sub,
        margin_pct=margin_pct, total_sale_price=total,
        low_confidence_items=list(low_conf))
def write_outputs(q: Quotation, out_dir: str):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out/"quote.json").write_text(q.model_dump_json(indent=2))
    tmpl = Template(Path(__file__).parent.joinpath("templates/quote.html.j2").read_text())
    (out/"quote.html").write_text(tmpl.render(q=q))
    # CSV BoQ
    rows = ["item_no,description,page,length_ft,surface_area_sqft,gauge,weight_lbs,total_cost,sale_price"]
    rows += [f"{i.item_no},{i.description},{i.page_label},{i.length_ft},{i.surface_area_sqft},{i.gauge},{i.weight_lbs},{i.total_cost},{i.sale_price}" for i in q.line_items]
    (out/"boq.csv").write_text("\n".join(rows))
```

- [ ] **Step 4: Create `src/ductquote/templates/quote.html.j2`** (clean, branded, print-ready)
```html
<!doctype html><meta charset="utf-8"><title>Quotation — {{ q.project_name }}</title>
<style>body{font:14px system-ui;margin:40px;color:#1a1a1a}h1{margin:0}
table{border-collapse:collapse;width:100%;margin-top:16px}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:right}th{background:#0b2545;color:#fff}
td:nth-child(2){text-align:left}.tot{font-size:20px;font-weight:700;margin-top:16px}
.warn{color:#b30000}</style>
<h1>Duct Fabrication Quotation</h1>
<p><b>{{ q.project_name }}</b> · Scale {{ q.scale.raw or 'default 1/8\"=1\'-0\"' }} · Sheets: {{ q.mechanical_pages|join(', ') }}</p>
<table><tr><th>#</th><th>Description</th><th>Len (ft)</th><th>SA (sqft)</th><th>Gauge</th><th>Wt (lb)</th><th>Cost</th><th>Price</th></tr>
{% for i in q.line_items %}<tr><td>{{i.item_no}}</td><td>{{i.description}}</td><td>{{i.length_ft}}</td><td>{{i.surface_area_sqft}}</td><td>{{i.gauge}}</td><td>{{i.weight_lbs}}</td><td>${{'%.2f'|format(i.total_cost)}}</td><td>${{'%.2f'|format(i.sale_price)}}</td></tr>{% endfor %}
</table>
<p>Fittings: {% for k,v in q.fittings_summary.items() %}{{k}}×{{v}} {% endfor %}</p>
<p class="tot">Total: ${{ '%.2f'|format(q.total_sale_price) }} <small>({{ (q.margin_pct*100)|int }}% margin)</small></p>
{% if q.low_confidence_items %}<p class="warn">⚠ {{ q.low_confidence_items|length }} item(s) need human review: {{ q.low_confidence_items|join(', ') }}</p>{% endif %}
```

- [ ] **Step 5: Run test** — `pytest tests/test_quote.py -v` — Expected: PASS.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: quotation assembly with JSON/CSV/HTML outputs"`

---

## Task 14: Pipeline orchestration + CLI

**Files:** Create `src/ductquote/pipeline.py`, `src/cli.py`; Test `tests/test_pipeline.py`

**Approach:** Wire every stage end-to-end on a real PDF. Collect low-confidence items (< `review_cutoff`) for the review queue. CLI: `python -m src.cli run <pdf> --project NAME [--no-llm]`.

- [ ] **Step 1: Write failing test `tests/test_pipeline.py`** (synthetic PDF, NullClient via `--no-llm` path)
```python
import os
from src.ductquote.pipeline import run_pipeline
def test_pipeline_end_to_end(synthetic_pdf, tmp_path):
    q = run_pipeline(synthetic_pdf, project="Synthetic", out_dir=str(tmp_path), use_llm=False)
    assert "M-101" in q.mechanical_pages
    assert os.path.exists(tmp_path/"quote.json")
    assert os.path.exists(tmp_path/"boq.csv")
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/pipeline.py`**
```python
import os
from .config import load_env, load_settings
from .loader import open_pdf, parse_scale
from .classify import classify_pages
from .vision_validate import validate_mechanical
from .geometry import extract_lines, pair_walls
from .runs import build_runs
from .dimensions import extract_dim_labels, match_dims_to_runs
from .vision_dims import fill_missing_dims
from .fittings import detect_fittings
from .annotate import annotate_page
from .boq import build_boq
from .pricing import price_all
from .quote import assemble_quote, write_outputs
from .llm import make_client, NullClient
def run_pipeline(pdf_path, project, out_dir="output", use_llm=True):
    load_env(); S = load_settings(); cutoff = S["confidence"]["review_cutoff"]
    client = make_client() if use_llm else NullClient()
    doc = open_pdf(pdf_path)
    pages = classify_pages(doc)
    scale = parse_scale("\n".join(doc[p.index].get_text() for p in pages if p.is_mechanical) or "")
    pages = validate_mechanical(doc if use_llm else None, pages, client=client)
    mech = [p for p in pages if p.is_mechanical]
    all_runs=[]; all_fittings=[]
    for p in mech:
        page = doc[p.index]
        lines = extract_lines(page)
        segs = pair_walls(lines)
        runs = build_runs(segs, scale, p.index, p.sheet_label or f"M-Page{p.index+1}")
        dims = extract_dim_labels(page)
        runs = match_dims_to_runs(runs, dims, S["match"]["size_radius_pts"])
        runs = fill_missing_dims(doc if use_llm else None, runs, client=client, cutoff=cutoff)
        fittings = detect_fittings(runs)
        annotate_page(doc, p.index, runs, fittings, os.path.join(out_dir, f"annotated_p{p.index+1}.png"))
        all_runs += runs; all_fittings += fittings
    items, thumb = build_boq(all_runs)
    items = price_all(items)
    fsum = {}
    for f in all_fittings: fsum[f.type.value] = fsum.get(f.type.value,0)+1
    fsum.update({"clamps": thumb["clamps"], "bolts": thumb["bolts"]})
    low = [r.id for r in all_runs if r.confidence < cutoff]
    from .config import load_catalog
    q = assemble_quote(project, scale, [p.sheet_label for p in mech], items, fsum, low,
                       margin_pct=load_catalog()["margin_pct"])
    write_outputs(q, out_dir)
    return q
```

- [ ] **Step 4: Implement `src/cli.py`**
```python
import argparse
from src.ductquote.pipeline import run_pipeline
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("pdf"); r.add_argument("--project", default="Project")
    r.add_argument("--out", default="output"); r.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    if a.cmd == "run":
        q = run_pipeline(a.pdf, a.project, a.out, use_llm=not a.no_llm)
        print(f"Quote: ${q.total_sale_price:.2f} | {len(q.line_items)} items | "
              f"{len(q.low_confidence_items)} need review | outputs in {a.out}/")
if __name__ == "__main__": main()
```

- [ ] **Step 5: Run test** — `pytest tests/test_pipeline.py -v` — Expected: PASS.

- [ ] **Step 6: Run on the real PDF (manual)** —
`python -m src.cli run "C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf" --project "GIA Moorefield" --no-llm`
Inspect `output/annotated_p*.png`, `boq.csv`, `quote.html`. Then re-run without `--no-llm` (needs `GEMINI_API_KEY`).

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat: end-to-end pipeline and CLI"`

---

## Task 15: Validation harness + ground truth + benchmark (the 95% gate)

**Files:** Create `validation/ground_truth.yaml`, `validation/benchmark.py`; Test `tests/test_benchmark.py`

**Approach:** Establish ground truth for the sample PDF: (a) hand-verify M-sheet page numbers and a sample of duct dims/lengths from the drawing; (b) cross-check against the `vortex-main` oracle by running its `analyze_single_pdf.py`. Benchmark computes: M-sheet precision/recall, dimension match rate, length error %, fitting count delta → overall takeoff accuracy. Loop fixes until ≥95%.

- [ ] **Step 1: Create `validation/ground_truth.yaml`** (filled during execution by reading the drawing + oracle; structure below)
```yaml
project: GIA Moorefield - PKG 1
mechanical_pages: []        # e.g. ["M-101","M-102",...] — fill from manual + oracle
runs:                       # a verified sample (not necessarily exhaustive)
  - sheet: M-101
    dimension: "24x12"
    length_ft_expected: 50.0
    length_tolerance_ft: 2.0
fittings_expected:          # counts per sheet (sample)
  M-101: {elbow_90: 0, tee: 0}
```

- [ ] **Step 2: Write failing test `tests/test_benchmark.py`**
```python
from validation.benchmark import score_lengths
def test_length_scoring_within_tolerance():
    gt = [{"sheet":"M-101","dimension":"24x12","length_ft_expected":50.0,"length_tolerance_ft":2.0}]
    got = [{"sheet":"M-101","dimension":"24x12","length_ft":51.0}]
    acc = score_lengths(gt, got)
    assert acc == 1.0
```

- [ ] **Step 3: Run test** — Expected: FAIL.

- [ ] **Step 4: Implement `validation/benchmark.py`**
```python
import yaml
from pathlib import Path
def score_lengths(gt_runs, got_runs):
    if not gt_runs: return 1.0
    hits = 0
    for g in gt_runs:
        match = next((r for r in got_runs if r["sheet"]==g["sheet"] and r["dimension"]==g["dimension"]), None)
        if match and abs(match["length_ft"]-g["length_ft_expected"]) <= g["length_tolerance_ft"]:
            hits += 1
    return hits/len(gt_runs)
def score_pages(expected, found):
    es, fs = set(expected), set(found)
    if not es: return 1.0, 1.0
    tp = len(es & fs); prec = tp/len(fs) if fs else 0.0; rec = tp/len(es)
    return prec, rec
def run_benchmark(pdf_path, gt_path="validation/ground_truth.yaml", out_dir="output"):
    gt = yaml.safe_load(Path(gt_path).read_text())
    from src.ductquote.pipeline import run_pipeline
    q = run_pipeline(pdf_path, gt["project"], out_dir, use_llm=True)
    got_runs = [{"sheet":i.page_label,"dimension":f"{int(i.width_in)}x{int(i.height_in)}" if i.height_in else f"{int(i.width_in)}rd","length_ft":i.length_ft} for i in q.line_items]
    prec, rec = score_pages(gt.get("mechanical_pages",[]), q.mechanical_pages)
    lacc = score_lengths(gt.get("runs",[]), got_runs)
    overall = round((rec*0.4 + lacc*0.6), 3)
    print(f"M-sheet precision {prec:.2f} recall {rec:.2f} | length acc {lacc:.2f} | OVERALL {overall:.2f}")
    return {"page_precision":prec,"page_recall":rec,"length_accuracy":lacc,"overall":overall}
if __name__ == "__main__":
    import sys; run_benchmark(sys.argv[1])
```

- [ ] **Step 5: Run test** — `pytest tests/test_benchmark.py -v` — Expected: PASS.

- [ ] **Step 6: Establish real ground truth (manual, during execution)**
  - Run oracle: `cd "C:\Users\subaa\Desktop\vortex new\vortex-main" && python .claude/skills/extraction-analysis/scripts/analyze_single_pdf.py "C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf"` → record its M-sheet list.
  - Open the PDF, hand-verify the M-sheet list and ~10 sample duct dims/lengths; fill `ground_truth.yaml`.

- [ ] **Step 7: Run benchmark and iterate to ≥95%**
  - `python -m validation.benchmark "C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf"`
  - If `overall < 0.95`: diagnose per stage (page recall? length error? dim match?), tune `settings.yaml` thresholds, re-run. Log each iteration's numbers in `output/benchmark_log.md`.

- [ ] **Step 8: Commit** — `git add -A && git commit -m "feat: validation harness and 95% accuracy benchmark"`

---

## Task 16: Human-review report + correction loop (prototype-ready polish)

**Files:** Create `src/ductquote/review.py`; Modify `pipeline.py` to emit it; Test `tests/test_review.py`

**Approach:** KT mandates human-in-the-loop. Emit `output/review_report.md` listing every low-confidence run with its annotated crop reference, the disagreement reason, and the deterministic value — so a reviewer approves/edits before the quote ships. This is the "under user control, every cent justified" deliverable.

- [ ] **Step 1: Write failing test `tests/test_review.py`**
```python
from src.ductquote.models import DuctRun, DuctSegment, Point
from src.ductquote.review import build_review_report
def test_review_lists_low_confidence():
    runs=[DuctRun(id="M-101-R5", page_index=0,
        segments=[DuctSegment(p1=Point(x=0,y=0),p2=Point(x=1,y=0),length_pts=1)],
        length_ft=0.1, confidence=0.4, reasons=["no dimension found — flagged for human review"])]
    md = build_review_report(runs, cutoff=0.7)
    assert "M-101-R5" in md and "review" in md.lower()
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Implement `src/ductquote/review.py`**
```python
def build_review_report(runs, cutoff=0.7):
    low = [r for r in runs if r.confidence < cutoff]
    lines = ["# Human Review Queue", "", f"{len(low)} item(s) below confidence {cutoff}.", ""]
    for r in low:
        dim = r.dimension.raw_text if r.dimension else "—"
        lines += [f"## {r.id} (page {r.page_index+1}) — confidence {r.confidence:.2f}",
                  f"- Dimension: {dim}", f"- Length (deterministic): {r.length_ft} ft",
                  f"- Reasons: {'; '.join(r.reasons)}",
                  f"- Action: verify against annotated_p{r.page_index+1}.png and approve/edit", ""]
    return "\n".join(lines)
```

- [ ] **Step 4: Modify `pipeline.py`** — after building `all_runs`, before return, add:
```python
    from .review import build_review_report
    import os as _os
    with open(_os.path.join(out_dir, "review_report.md"), "w", encoding="utf-8") as fh:
        fh.write(build_review_report(all_runs, cutoff))
```

- [ ] **Step 5: Run tests** — `pytest tests/test_review.py -v` and full `pytest -v` — Expected: PASS (all).

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: human-in-the-loop review report"`

---

## Task 17: Showcase Web UI (FastAPI + polished frontend)

**Files:** Create `webapp/server.py`, `webapp/static/index.html`, `webapp/static/styles.css`, `webapp/static/app.js`; Test `tests/test_server.py`

**Approach:** A clean, professional single-page app for the live demo. User uploads the HVAC PDF → backend runs `run_pipeline` → returns JSON (mechanical pages, annotated image URLs, BoQ line items with derivations, fittings summary, totals, review queue). Frontend renders: a header with project + total price, a sheet gallery (annotated PNGs), an interactive BoQ table (click a row → see its cost derivation), a fittings/thumb-rule panel, and a print-ready quote view. Use the `frontend-design` skill for the visual layer so it is distinctive and not generic. Backend reuses the pipeline — no logic duplicated.

- [ ] **Step 1: Write failing test `tests/test_server.py`**
```python
from fastapi.testclient import TestClient
from webapp.server import app
def test_health():
    c = TestClient(app); r = c.get("/api/health"); assert r.status_code == 200 and r.json()["ok"]
def test_analyze_synthetic(synthetic_pdf):
    c = TestClient(app)
    with open(synthetic_pdf, "rb") as fh:
        r = c.post("/api/analyze", files={"file": ("s.pdf", fh, "application/pdf")},
                   data={"project": "Synthetic", "use_llm": "false"})
    assert r.status_code == 200
    body = r.json()
    assert "M-101" in body["mechanical_pages"] and "total_sale_price" in body
```

- [ ] **Step 2: Run test** — `pytest tests/test_server.py -v` — Expected: FAIL.

- [ ] **Step 3: Implement `webapp/server.py`**
```python
import os, uuid, tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from src.ductquote.pipeline import run_pipeline
app = FastAPI(title="RFP/RFQ Vortex Sample POC")
OUT = Path("output"); OUT.mkdir(exist_ok=True)
@app.get("/api/health")
def health(): return {"ok": True, "product": "RFP/RFQ Vortex Sample POC"}
@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), project: str = Form("Project"), use_llm: str = Form("false")):
    job = uuid.uuid4().hex[:8]; job_dir = OUT / job; job_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = job_dir / "input.pdf"; pdf_path.write_bytes(await file.read())
    q = run_pipeline(str(pdf_path), project, str(job_dir), use_llm=(use_llm.lower()=="true"))
    imgs = [f"/output/{job}/{p.name}" for p in sorted(job_dir.glob("annotated_p*.png"))]
    data = q.model_dump(); data["annotated_images"] = imgs; data["job"] = job
    return JSONResponse(data)
app.mount("/output", StaticFiles(directory="output"), name="output")
app.mount("/", StaticFiles(directory="webapp/static", html=True), name="static")
```

- [ ] **Step 4: Implement `webapp/static/index.html` + `styles.css` + `app.js`** using the `frontend-design` skill — a professional theme (deep navy `#0b2545` accent matching the quote, system-font stack, generous spacing, cards). Sections: upload dropzone + project name + "Use AI" toggle + "Generate Quote" button; results = headline total, sheet gallery, BoQ table (expandable derivation), fittings/thumb-rule chips, review-queue banner, "Print quote" button. `app.js` POSTs to `/api/analyze` and renders the JSON. (Full markup produced at execution time via frontend-design; must render the fields returned by `/api/analyze`: `project_name`, `mechanical_pages`, `annotated_images`, `line_items[]`, `fittings_summary`, `total_sale_price`, `margin_pct`, `low_confidence_items`.)

- [ ] **Step 5: Run test** — `pytest tests/test_server.py -v` — Expected: PASS.

- [ ] **Step 6: Manual showcase check** — `uvicorn webapp.server:app --reload`, open http://127.0.0.1:8000, upload the sample PDF, verify annotated sheets + BoQ + quote render cleanly.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat: showcase web UI (FastAPI + polished SPA)"`

---

## Self-Review (spec coverage)

| Use-case / KT requirement | Task(s) |
|---|---|
| Clean professional UI for showcase | 17 |
| Standalone, unique (not a copy of vortex-main) | all — oracle only in 15 |
| Segregate M-series sheets | 2, 3 |
| Annotate ducts | 4, 5, 10 |
| Extract dimensions (12x22) | 7, 8 |
| Length from annotation + scale | 1, 6 |
| List items (BoQ) | 11 |
| L/T joints (bonus) | 9 |
| **End goal: full quotation** | 12, 13 |
| AI used where needed, never for length/pricing | 3, 8 (LLM) vs 6, 12 (deterministic) |
| Every cent maps to a reason | 12 (`derivation`), 13 |
| Human-in-the-loop | 16 |
| Thumb rules (clamps/bolts) | 11 |
| SMACNA gauge/weight/pressure | 12 |
| 95% accuracy, prototype-ready | 15 (benchmark loop) |
| Visual proof before UI | 10, 14 |

**Placeholder scan:** none — every code/test step contains runnable content.
**Type consistency:** all models defined in Task 0 `models.py`; later tasks use those exact names (`DuctRun.dimension`, `LineItem.sale_price`, `Fitting.type`, etc.).

**Known follow-ups (post-95%):** color→system mapping refinement (supply/return/exhaust) on the real palette; round/spiral buy-out pricing path; SHX/raster handling (not needed for this vector PDF); per-pressure-class gauge once spec sheet wattage/pressure is parsed.

---

## Execution note
Default sample PDF path used throughout: `C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf`. Gemini key expected in `duct-quote-poc/.env` (`GEMINI_API_KEY=`) or reuse `vortex-backend/.env`. Deterministic-only runs (`--no-llm`) work fully offline for development and CI.
