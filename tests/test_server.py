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
