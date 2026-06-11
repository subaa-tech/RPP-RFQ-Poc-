"""Drive the ALREADY-RUNNING live server (http://127.0.0.1:8000) in a browser:
upload the sample PDF, verify the quotation renders, screenshot the live UI."""
import glob
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PDF = r"C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf"
URL = "http://127.0.0.1:8000"


def find_chrome():
    if os.environ.get("PW_EXECUTABLE"):
        return os.environ["PW_EXECUTABLE"]
    base = os.path.expandvars(r"%USERPROFILE%\AppData\Local\ms-playwright")
    for pat in ("chromium-*/chrome-win64/chrome.exe", "chromium-*/chrome-win/chrome.exe"):
        hits = sorted(glob.glob(os.path.join(base, pat)))
        if hits:
            return hits[-1]
    return None


with sync_playwright() as p:
    exe = find_chrome()
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 2000})
    page.goto(URL)
    page.wait_for_selector(".badge.ok", timeout=10000)
    print("[live] engine online at", URL)
    page.set_input_files("#fileInput", PDF)
    page.fill("#project", "GIA Moorefield - PKG 1")
    page.click("#runBtn")
    page.wait_for_selector("#report:not([hidden])", timeout=420000)
    total = page.inner_text("#qhTotal")
    items = page.eval_on_selector_all("#boqBody tr.row", "els => els.length")
    print(f"[live] TOTAL={total} | line items={items}")
    page.screenshot(path=str(ROOT / "output" / "live_check.png"), full_page=True)
    print("[live] screenshot -> output/live_check.png")
    browser.close()
    print("[live] OK")
