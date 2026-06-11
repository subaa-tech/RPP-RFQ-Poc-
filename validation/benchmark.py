import yaml
from pathlib import Path


def score_lengths(gt_runs, got_runs):
    if not gt_runs:
        return 1.0
    hits = 0
    for g in gt_runs:
        match = next((r for r in got_runs
                      if r["sheet"] == g["sheet"] and r["dimension"] == g["dimension"]), None)
        if match and abs(match["length_ft"] - g["length_ft_expected"]) <= g["length_tolerance_ft"]:
            hits += 1
    return hits / len(gt_runs)


def score_pages(expected, found):
    es, fs = set(expected), set(found)
    if not es:
        return 1.0, 1.0
    tp = len(es & fs)
    prec = tp / len(fs) if fs else 0.0
    rec = tp / len(es)
    return prec, rec


def run_benchmark(pdf_path, gt_path="validation/ground_truth.yaml", out_dir="output", use_llm=True):
    gt = yaml.safe_load(Path(gt_path).read_text())
    from src.ductquote.pipeline import run_pipeline
    q = run_pipeline(pdf_path, gt["project"], out_dir, use_llm=use_llm)
    got_runs = [{
        "sheet": i.page_label,
        "dimension": f"{int(i.width_in)}x{int(i.height_in)}" if i.height_in else f"{int(i.width_in)}rd",
        "length_ft": i.length_ft,
    } for i in q.line_items]
    prec, rec = score_pages(gt.get("mechanical_pages", []), q.mechanical_pages)
    lacc = score_lengths(gt.get("runs", []), got_runs)
    overall = round((rec * 0.4 + lacc * 0.6), 3)
    print(f"M-sheet precision {prec:.2f} recall {rec:.2f} | length acc {lacc:.2f} | OVERALL {overall:.2f}")
    return {"page_precision": prec, "page_recall": rec, "length_accuracy": lacc, "overall": overall}


if __name__ == "__main__":
    import sys
    run_benchmark(sys.argv[1], use_llm=("--no-llm" not in sys.argv))
