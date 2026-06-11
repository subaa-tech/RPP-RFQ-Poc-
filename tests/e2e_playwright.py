"""End-to-end UI test with Playwright.

Launches the FastAPI server, drives the browser to upload the sample Vortex PDF,
waits for the quotation to render, asserts key elements, and screenshots the UI.

Run:
    python -m playwright install chromium      # once
    python tests/e2e_playwright.py             # uses the real sample PDF
    python tests/e2e_playwright.py --synthetic # fast synthetic PDF
"""
import glob
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL_PDF = r"C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf"
PORT = 8077


def find_chrome():
    """Locate an already-installed Playwright chromium executable (fallback when
    the exact browser revision for the installed package isn't downloaded)."""
    if os.environ.get("PW_EXECUTABLE"):
        return os.environ["PW_EXECUTABLE"]
    base = os.path.expandvars(r"%USERPROFILE%\AppData\Local\ms-playwright")
    for pat in ("chromium-*/chrome-win64/chrome.exe", "chromium-*/chrome-win/chrome.exe"):
        hits = sorted(glob.glob(os.path.join(base, pat)))
        if hits:
            return hits[-1]
    return None


def wait_port(port, timeout=40):
    for _ in range(timeout * 2):
        try:
            with socket.create_connection(("127.0.0.1", port), 1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    from playwright.sync_api import sync_playwright

    synthetic = "--synthetic" in sys.argv
    if synthetic:
        from tests.fixtures.make_synthetic_pdf import build
        pdf = str(ROOT / "output" / "_e2e_synth.pdf")
        Path(pdf).parent.mkdir(exist_ok=True)
        build(pdf)
    else:
        pdf = REAL_PDF

    srv = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "webapp.server:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(ROOT),
    )
    try:
        assert wait_port(PORT), "server did not start"
        with sync_playwright() as p:
            exe = find_chrome()
            launch_kw = {"executable_path": exe} if exe else {}
            if exe:
                print(f"[e2e] using browser: {exe}")
            browser = p.chromium.launch(**launch_kw)
            page = browser.new_page(viewport={"width": 1440, "height": 1900})
            page.goto(f"http://127.0.0.1:{PORT}")
            page.wait_for_selector(".badge.ok", timeout=10000)
            print("[e2e] engine online")
            page.set_input_files("#fileInput", pdf)
            page.fill("#project", "GIA Moorefield - PKG 1")
            page.click("#runBtn")
            print("[e2e] analysis started, waiting for report...")
            page.wait_for_selector("#report:not([hidden])", timeout=420000)
            total = page.inner_text("#qhTotal")
            sheets = page.inner_text(".kpi:nth-child(2) .v")
            items = page.eval_on_selector_all("#boqBody tr.row", "els => els.length")
            print(f"[e2e] TOTAL={total} | M-sheets={sheets} | line items={items}")
            out_png = ROOT / "output" / "ui_demo.png"
            page.screenshot(path=str(out_png), full_page=True)
            print(f"[e2e] screenshot -> {out_png}")
            assert "$" in total, "no quote total rendered"

            # --- human-in-the-loop: edit + exclude + recompute + approve ---
            incs = page.query_selector_all("#boqBody tr.row .inc")
            lens = page.query_selector_all("#boqBody tr.row .len:not([disabled])")
            if lens:
                lens[0].fill("99")                      # edit a duct length
            if len(incs) > 1:
                incs[1].uncheck()                       # reject a line item
            page.fill("#marginInput", "30")             # change margin
            page.click("#recomputeBtn")
            page.wait_for_timeout(1200)
            page.click("#approveBtn")
            page.wait_for_selector("#approvedBanner:not([hidden])", timeout=15000)
            approved_total = page.inner_text("#qhTotal")
            print(f"[e2e] review+approve OK | approved total={approved_total}")
            page.screenshot(path=str(ROOT / "output" / "ui_approved.png"), full_page=True)
            assert "$" in approved_total
            browser.close()
        print("[e2e] PASS")
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
