# READ-ONLY: check for OCG layers and per-drawing layer tags (key to duct isolation).
import sys, collections
sys.path.insert(0, ".")
import fitz
doc = fitz.open(r"C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf")
ocgs = doc.get_ocgs()
print("OCG COUNT:", len(ocgs))
for k, v in list(ocgs.items())[:40]:
    print("  OCG:", v.get("name"))

# Per-drawing layer tags on a couple of M pages
for pidx in (1, 2):
    page = doc[pidx]
    layers = collections.Counter()
    drs = page.get_drawings()
    for d in drs:
        layers[d.get("layer")] += 1
    print(f"\nPage {pidx+1}: drawings={len(drs)} distinct layer tags={len(layers)}")
    for name, cnt in layers.most_common(20):
        print(f"   layer={name!r}: {cnt}")
doc.close()
