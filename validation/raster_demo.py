"""Prove the raster path on a REAL sheet: flatten M-2.03 to a raster-only image,
then run page-type triage + OpenCV geometry on it."""
import sys
import fitz
sys.path.insert(0, ".")
from src.ductquote.pagetype import page_type
from src.ductquote.raster import extract_lines_raster, have_cv2

src = fitz.open(sys.argv[1])
page = src[3]                      # M-2.03 (real vector duct plan)
print("original page_type:", page_type(page))

# flatten to a raster-only one-page PDF
pix = page.get_pixmap(dpi=150)
out = fitz.open()
op = out.new_page(width=page.rect.width, height=page.rect.height)
op.insert_image(op.rect, pixmap=pix)
rp = out[0]

print("flattened page_type:", page_type(rp))
print("opencv available:", have_cv2())
lines = extract_lines_raster(rp)
print("raster Hough line segments detected:", len(lines))
src.close()
out.close()
