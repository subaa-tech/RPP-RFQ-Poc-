import os
from src.ductquote.pipeline import run_pipeline


def test_pipeline_end_to_end(synthetic_pdf, tmp_path):
    q = run_pipeline(synthetic_pdf, project="Synthetic", out_dir=str(tmp_path), use_llm=False)
    assert "M-101" in q.mechanical_pages
    assert os.path.exists(tmp_path / "quote.json")
    assert os.path.exists(tmp_path / "boq.csv")
