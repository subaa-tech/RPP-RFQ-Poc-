# READ-ONLY diagnostic: understand real M-page geometry to tune filters.
import sys, collections
sys.path.insert(0, ".")
from src.ductquote.loader import open_pdf, parse_scale
from src.ductquote.classify import classify_pages
from src.ductquote.geometry import extract_lines

doc = open_pdf(r"C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf")
pages = classify_pages(doc)
mech = [p for p in pages if p.is_mechanical]
print("MECH PAGES:", [(p.index+1, p.sheet_label, round(p.score,2)) for p in mech])
print("ALL LABELS:", [(p.index+1, p.sheet_label, p.is_mechanical, round(p.score,2)) for p in pages])

for p in mech[:3]:
    page = doc[p.index]
    draws = page.get_drawings()
    lines = extract_lines(page)
    colors = collections.Counter()
    for d in draws:
        for it in d["items"]:
            if it[0] == "l":
                colors[tuple(round(c,2) for c in (d.get("color") or ()))] += 1
    print(f"\nPage {p.index+1} {p.sheet_label}: drawings={len(draws)} kept_lines={len(lines)}")
    print("  top line colors:", colors.most_common(8))
doc.close()
