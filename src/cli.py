import argparse
from src.ductquote.pipeline import run_pipeline


def main():
    ap = argparse.ArgumentParser(prog="ductquote", description="RFP/RFQ Vortex Sample POC")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("pdf")
    r.add_argument("--project", default="Project")
    r.add_argument("--out", default="output")
    r.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    if a.cmd == "run":
        q = run_pipeline(a.pdf, a.project, a.out, use_llm=not a.no_llm)
        print(f"Quote: ${q.total_sale_price:.2f} | {len(q.line_items)} items | "
              f"{len(q.low_confidence_items)} need review | outputs in {a.out}/")


if __name__ == "__main__":
    main()
