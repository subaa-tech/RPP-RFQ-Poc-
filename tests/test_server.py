from fastapi.testclient import TestClient
from webapp.server import app


def test_health():
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"]


def test_analyze_synthetic(synthetic_pdf):
    c = TestClient(app)
    with open(synthetic_pdf, "rb") as fh:
        r = c.post("/api/analyze", files={"file": ("s.pdf", fh, "application/pdf")},
                   data={"project": "Synthetic", "use_llm": "false"})
    assert r.status_code == 200
    body = r.json()
    assert "M-101" in body["mechanical_pages"] and "total_sale_price" in body
    assert body.get("sheets") and body["sheets"][0]["type"] in ("vector", "raster", "shx")


def test_reprice_excludes_edits_and_margin():
    c = TestClient(app)
    items = [
        {"category": "duct", "shape": "rect", "width_in": 24, "height_in": 12, "length_ft": 50,
         "included": True, "page_label": "M-1"},
        {"category": "duct", "shape": "rect", "width_in": 10, "height_in": 10, "length_ft": 10,
         "included": False, "page_label": "M-1"},   # reviewer rejected this one
    ]
    r = c.post("/api/reprice", json={"line_items": items, "margin_pct": 0.30, "finalize": True})
    assert r.status_code == 200
    b = r.json()
    assert len(b["included_items"]) == 1        # excluded item dropped
    assert b["approved"] is True
    assert b["margin_pct"] == 0.30
    assert b["total_sale_price"] > b["subtotal_cost"]   # margin applied
