# RFP/RFQ Vortex Sample POC

Turns a Vortex **HVAC mechanical drawing PDF** into a fully-priced, human-reviewable
**duct fabrication quotation** — segregating the M-series sheets, annotating duct runs,
extracting dimensions and lengths, detecting fittings, and applying the SMACNA pricing
chain. Built as a standalone POC (no Django/Celery/UI framework); the existing
`vortex-main` system is used only as an accuracy oracle, never copied.

> Scope source: KT session + lead use-case. End goal: **quotation**. Target: **≥95%**
> takeoff accuracy on the sample dataset. See `docs/PLAN.md` and `docs/FINDINGS.md`.

## What it does (pipeline)

```
PDF → ① segregate M-series sheets → ② detect + pair duct walls → ③ read dimensions (12x22)
    → ④ length from scale (1/8"=1'-0") → ⑤ detect L/T/reducer fittings → ⑥ Bill of Quantities
    → ⑦ SMACNA pricing (area→gauge→weight→material+labor+overhead+freight) → ⑧ margin → QUOTE
```

**Deterministic** for all geometry, length and pricing (every cent carries a cited
derivation). **AI (Gemini)** is used only for sheet validation and ambiguous
dimension/fitting reads — never for length or pricing (per KT). Runs fully offline with
`--no-llm`.

## Quick start

```bash
pip install -r requirements.txt

# CLI (deterministic, offline)
python -m src.cli run "<path-to>.pdf" --project "GIA Moorefield" --no-llm
#   -> output/: annotated_p*.png, boq.csv, quote.json, quote.html, review_report.md

# Web UI (showcase)
uvicorn webapp.server:app --reload
#   -> http://127.0.0.1:8000  (upload PDF, see annotated sheets + BoQ + quotation)
```

Enable AI assist: set `GEMINI_API_KEY` in `.env` (copy `.env.example`) and tick "AI assist"
in the UI (or drop `--no-llm`).

## Tests

```bash
python -m pytest -q                       # unit + API tests
python tests/e2e_playwright.py            # browser e2e on the real PDF
python tests/e2e_playwright.py --synthetic  # fast synthetic e2e
python -m validation.benchmark "<pdf>"    # accuracy vs validation/ground_truth.yaml
```

## Layout

| Path | Role |
|------|------|
| `src/ductquote/` | pipeline modules (loader, classify, geometry, runs, dimensions, fittings, pricing, quote) |
| `src/ductquote/llm.py` | swappable LLM interface (Gemini / Null) |
| `webapp/` | FastAPI server + single-page UI |
| `config/` | `settings.yaml` (thresholds) + `pricing_catalog.yaml` (SMACNA defaults) |
| `validation/` | ground truth + benchmark harness |
| `docs/` | implementation plan + findings |

## Notes / limits

- Tuned for **true-vector** sheets (this dataset). Raster/SHX inputs are out of scope here.
- Duct detection is **label-anchored**: a run becomes a priced line item only when a
  dimension label claims it — this keeps the takeoff precise.
- Pricing-catalog values are indicative SMACNA defaults in `config/pricing_catalog.yaml`;
  point them at live supplier contracts before real bids.
