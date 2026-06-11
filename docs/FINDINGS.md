# POC Findings — Vortex HVAC Duct Takeoff

**POC goal (assigned to Subaa):** From a Vortex HVAC drawing set →
1. Segregate the **M-series** (mechanical) drawings
2. Annotate **ducts** → extract **dimensions** (e.g. `12x22`)
3. Compute **length** from annotation geometry + drawing **scale**
4. **List the items** (BoQ)
5. Bonus: detect **L-joints, T-joints**, reducers, etc.

This doc captures what was learned going through all inputs **before** any implementation.

---

## 1. The sample input — triaged (read-only)

**File:** `C:\Users\subaa\Downloads\GIA Moorefield - PKG 1 - Revised x2 spec sheet.pdf`
(byte-identical duplicate of `2026.01.17Mechanical PKG 1 Core and Shell full.pdf` — same 3,556,117 bytes)

| Property | Value |
|----------|-------|
| Pages | 11 |
| Producer | Bluebeam (Brewery 5.0 / Stapler) |
| Type | **True VECTOR** on every page (text + vector paths) — the *easiest* KT category |
| Page size | 3024 × 2160 pt (~42"×30" sheets) |
| Vector density | 2,400–40,000 drawing items/page |
| Embedded images | 1/page (likely a background/logo, not the drawing) |
| **Scale found** | **`1/8" = 1'-0"`** (appears 4×) — the exact KT example |

**Implication:** This is the best-case path. Per the KT, vector + PyMuPDF = highest accuracy (~90%+). No raster CV or SHX-stroke math needed for this file. Scale parsing is straightforward.

> ⚠️ Sheet-ID detection needs work: the quick regex only reliably found scale, not the `M-xxx` sheet numbers — those live in the title block (right edge), which needs targeted title-block parsing (the existing system already solves this — see §2).

---

## 2. KEY DISCOVERY: this POC is already fully built in `vortex-main`

There is a **complete production system** at `C:\Users\subaa\Desktop\vortex new\vortex-main` (Django + FastAPI + Celery workers + React, deployed on GCP) called **Vortex AI** — "AI-powered estimation and pricing automation for Vortex Metal Manufacturing (duct fabrication)." It already implements **all 5 POC goals** using exactly the KT philosophy (vector-first deterministic, Gemini only for validation/ambiguity).

### Mapping POC goals → existing implementation

| POC goal | Where it's implemented | Approach | Det. vs LLM |
|----------|------------------------|----------|-------------|
| **1. M-sheet segregation** | `vortex-worker-extraction/services/classifier.py` + `vision_validator.py`; also `src/hvac_extractor/page_classifier.py` | 3-stage filter: M-label regex in title block (≥18pt) → PLAN/scale keyword check → geometry signals (dim labels + ≥10k drawings + CFM). Tesseract OCR fallback for SHX. Then Gemini 2.5 Flash thumbnail-grid validation, **fail-closed**. | 95% det / 5% LLM |
| **2. Duct detection/annotation** | `src/hvac_extractor/paths.py`, `ocg_converter.py`, `vision.py` | PyMuPDF `get_drawings()` → weight/brightness filters → **parallel-line pairing** (two duct walls, gap 3.5–50pt) → synthetic OCG layers. Color→system (red=exhaust, blue=supply). | 85% det / 15% LLM |
| **3. Dimension extraction (`12x22`)** | `src/hvac_extractor/text.py`, `vision.py` | Regex on text spans: `(\d+)["]?\s*[x×X]\s*(\d+)` for rect, `Ø/DIA` for round. Match label→nearest duct within ~150pt. Gemini fallback for garbled labels. Cap 96". | 80% det / 20% LLM |
| **4. Scale + length** | `src/hvac_extractor/loader.py` (`parse_scale`), `paths.py` | Regex `(\d+)/(\d+)"=(\d+)'-(\d+)"` → points_to_feet. At 1/8": `9 pt = 1 ft` (=1/9 ft/pt). Length = Euclidean dist × factor. **100% deterministic.** | 100% det |
| **5. Fitting/joint detection** | `src/hvac_extractor/classifier.py`, `vision.py` | Junction discovery (endpoint→body, 15pt tol) → angle classify: 90°/45° elbow, **tee** (collinear+perp branch), **wye**, transition, reducer. Gemini only for uncertain tiers. | 75% det / 25% LLM |
| **(BoQ + pricing)** | `recap_calc.py`, `quotation_calc.py`, `duct_pricing_reference.docx.md` | SMACNA chain: dims→perimeter→surface area→gauge(by pressure)→weight→material+labor+overhead+freight→margin. Fittings via equivalent-length. | 100% det |

### Pipeline orchestration
`vortex-worker-extraction/tasks/extract_diagrams.py` (Celery): load PDF → classify pages → Gemini validate → render/store → hvac_extractor (ducts, dims, scale/length, fittings, pressure) → quotation. Workers split by Redis queue: `extraction`, `detection`, `recap`, `specs`, `sync`, analytics.

### Pricing grounding (SMACNA)
`duct_pricing_reference.docx.md` is a full engineering reference: pricing chain, rectangular/round formulas, gauge-by-pressure table (SMACNA Table 1-1), gauge weight factors, fitting equivalent lengths, material $/lb ranges, waste up-rules, labor (Pitts/welded), overhead/freight, markup-vs-margin, worked example ($11.82/LF for a 24×12×50ft duct).

---

## 3. CONFIRMED END GOAL (locked 2026-06-11)

**Decision:** Standalone, from-scratch learning/demo POC → **full quotation**.

- **Approach:** Option A — a clean standalone Python project (no Django/Celery/Redis/UI). Built from scratch for *learning the domain*, with visual proof at each step.
- **Output scope:** the **full chain** — takeoff **and** SMACNA pricing **and** final quotation with margin.
- **Reference oracle:** the existing `vortex-main` `hvac_extractor` + `duct_pricing_reference.docx.md` are used to *check accuracy against*, not copied wholesale.
- **Primary input:** the `GIA Moorefield - PKG 1` 11-page vector PDF.

### Pipeline the POC will implement
```
PDF
 → ① segregate M-series mechanical sheets
 → ② detect + annotate duct runs   ──► annotated image (visual proof)
 → ③ extract dimensions (12x22)
 → ④ scale + length (1/8"=1'-0" → feet)
 → ⑤ detect L/T joints, reducers (bonus)
 → ⑥ Bill of Quantities (item list)
 → ⑦ SMACNA pricing: dims → surface area → gauge → weight → material+labor+overhead+freight
 → ⑧ apply margin → FINAL QUOTATION
```
Steps ①–⑥ = deterministic vector takeoff. ⑦–⑧ = deterministic pricing arithmetic. Gemini only for validation / ambiguous dims / ambiguous fittings — **never** for length or pricing (per KT).

---

## 4. Open items before building
- [ ] Confirm with the assigner: standalone POC (A) vs reuse (B) vs specific slice (C)?
- [ ] Is the deliverable just M-sheet + duct dims + length + item list, or also pricing/BoQ value?
- [ ] Build a robust **title-block sheet-number** parser (quick triage regex was insufficient).
- [ ] Decide vector-only (sufficient for this PDF) vs. also handle raster/SHX (not needed for this file).
- [ ] Ground truth for accuracy: is there a Trimble takeoff / reference for this exact PDF to measure the 90% benchmark against?

---
*Status: investigation complete, nothing implemented. Awaiting direction on Option A/B/C.*
