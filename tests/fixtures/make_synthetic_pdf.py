import fitz


def build(path: str) -> None:
    """Build a deterministic 2-page PDF for unit tests.

    Page 0: M-101 HVAC PLAN, scale 1/8"=1'-0", two blue parallel duct walls
            90pt long 18pt apart, labelled 12x18.
    Page 1: A-201 ARCH PLAN (non-mechanical).
    """
    doc = fitz.open()
    p = doc.new_page(width=800, height=600)
    p.insert_text((650, 560), "M-101", fontsize=20)
    p.insert_text((600, 580), "HVAC PLAN", fontsize=10)
    p.insert_text((300, 580), '1/8" = 1\'-0"', fontsize=10)
    p.draw_line((100, 200), (190, 200), color=(0, 0, 1), width=1)   # blue = supply
    p.draw_line((100, 218), (190, 218), color=(0, 0, 1), width=1)
    p.insert_text((130, 195), "12x18", fontsize=8)
    p2 = doc.new_page(width=800, height=600)
    p2.insert_text((650, 560), "A-201", fontsize=20)
    p2.insert_text((600, 580), "ARCH PLAN", fontsize=10)
    doc.save(path)
    doc.close()


def build_raster(path: str) -> None:
    """A flattened RASTER page: two duct walls + a size label, drawn then flattened to a
    single image (no vector lines or extractable text)."""
    src = fitz.open()
    sp = src.new_page(width=400, height=300)
    sp.draw_line((60, 150), (340, 150), color=(0, 0, 0), width=2)
    sp.draw_line((60, 166), (340, 166), color=(0, 0, 0), width=2)
    sp.insert_text((180, 142), '12"x18"', fontsize=11)
    pix = sp.get_pixmap(dpi=150)
    out = fitz.open()
    op = out.new_page(width=400, height=300)
    op.insert_image(op.rect, pixmap=pix)
    out.save(path)
    out.close()
    src.close()


def build_shx(path: str) -> None:
    """An SHX-like page: lots of vector geometry, no extractable text."""
    doc = fitz.open()
    p = doc.new_page(width=400, height=300)
    for i in range(60):
        x = 20 + i * 5
        p.draw_line((x, 40), (x, 260), width=0.5)
    doc.save(path)
    doc.close()


if __name__ == "__main__":
    build("synthetic.pdf")
