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


if __name__ == "__main__":
    build("synthetic.pdf")
