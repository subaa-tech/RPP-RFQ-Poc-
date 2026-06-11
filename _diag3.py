# READ-ONLY: how many duct dimension labels are detectable per mech page?
import sys
sys.path.insert(0, ".")
from src.ductquote.loader import open_pdf
from src.ductquote.classify import classify_pages
from src.ductquote.dimensions import extract_dim_labels

doc = open_pdf(r"C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf")
pages = classify_pages(doc)
mech = [p for p in pages if p.is_mechanical]
for p in mech:
    labels = extract_dim_labels(doc[p.index])
    samples = [f"{l.raw_text}@({int(l.center.x)},{int(l.center.y)})" for l in labels[:12]]
    print(f"Page {p.index+1} {p.sheet_label}: {len(labels)} dim labels | {samples}")
doc.close()
