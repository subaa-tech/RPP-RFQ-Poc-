import sys, time
sys.path.insert(0, ".")
from src.ductquote.loader import open_pdf
from src.ductquote.classify import classify_pages
from src.ductquote.geometry import extract_lines, pair_walls
from src.ductquote.dimensions import extract_dim_labels
from src.ductquote.runs import build_runs
from src.ductquote.models import Scale

doc = open_pdf(r"C:\Users\subaa\Downloads\2026.01.17Mechanical PKG 1 Core and Shell full.pdf")
scale = Scale(raw="", points_to_feet=1/9, source="default")
for pidx in (2, 3):  # heaviest pages (0-based -> pages 3,4)
    page = doc[pidx]
    t = time.time(); draws = page.get_drawings(); t_draw = time.time()-t
    t = time.time(); lines = extract_lines(page); t_lines = time.time()-t
    t = time.time(); dims = extract_dim_labels(page); t_dims = time.time()-t
    anchors = [d.center for d in dims if d.center]
    t = time.time(); segs = pair_walls(lines, anchors=anchors); t_pair = time.time()-t
    t = time.time(); runs = build_runs(segs, scale, pidx, "M"); t_runs = time.time()-t
    print(f"PAGE {pidx+1}: draws={len(draws)} lines={len(lines)} dims={len(dims)} segs={len(segs)} runs={len(runs)}")
    print(f"   get_drawings={t_draw:.1f}s extract_lines={t_lines:.1f}s dims={t_dims:.1f}s pair={t_pair:.1f}s build_runs={t_runs:.1f}s")
doc.close()
