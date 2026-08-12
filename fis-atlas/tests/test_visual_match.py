from fis import visual, match, registry
from fis.match import VisualItem


def test_hamming_and_same_picture():
    assert visual.hamming(0b1010, 0b1000) == 1
    assert visual.is_same_picture(0xFFFF0000FFFF0000, 0xFFFF0000FFFF0001, threshold=2)
    assert not visual.is_same_picture(0x0, 0xFFFFFFFFFFFFFFFF, threshold=10)


def test_dhash_is_deterministic():
    gray = [i % 7 for i in range(9 * 8)]
    assert visual.dhash_from_gray(gray, 9, 8) == visual.dhash_from_gray(gray, 9, 8)


def test_pdf_page_and_images_group_but_pdf_stays_a_pointer():
    base = 0xA1B2C3D4E5F60718
    items = [
        VisualItem("PG", "pdf_page", base, page=3, document_id="D004"),   # page 3 of a deck
        VisualItem("O2", "png", base ^ 0b11, page=3, path="D:/slide_03.png"),
        VisualItem("O3", "webp", base ^ 0b101, page=3, path="Z:/slide_03.webp"),
        VisualItem("O4", "png", 0x0F0F0F0F0F0F0F0F, page=1, path="D:/unrelated.png"),
    ]
    groups = match.build_groups(items, threshold=10)
    assert len(groups) == 1
    g = groups[0]
    reps = {m.representation for m in g.members}
    assert reps == {"pdf_page", "png", "webp"}
    # the pdf member is a POINTER to (document, page), never the whole deck
    m = g.manifest()["members"]
    pdf = [x for x in m if x["representation"] == "pdf_page"][0]
    assert pdf["document"] == "D004" and pdf["page"] == 3 and "path" not in pdf
    names = g.names()
    assert names["PG"].endswith(".pdf-page.json")     # pointer file, not G011-A.pdf


def test_document_identity_is_separate_from_visual_group():
    deck = match.Document(doc_id="D004", path="H:/deck.pdf", pages=12)
    assert deck.doc_id == "D004" and deck.pages == 12
    # a 12-page deck is ONE document but can appear in many visual groups
    slide1, slide2 = 0x0000FFFF0000FFFF, 0xFFFF0000FFFF0000   # 32 bits apart
    items = [
        VisualItem("PG1", "pdf_page", slide1, page=1, document_id="D004"),
        VisualItem("I1", "png", slide1, page=1, path="a.png"),
        VisualItem("PG2", "pdf_page", slide2, page=2, document_id="D004"),
        VisualItem("I2", "png", slide2, page=2, path="b.png"),
    ]
    groups = match.build_groups(items, threshold=2)
    assert len(groups) == 2                            # two slides -> two groups
    docs = {mm["document"] for g in groups for mm in g.manifest()["members"]
            if mm["representation"] == "pdf_page"}
    assert docs == {"D004"}                            # same deck, two visual identities


def test_stage_plan_copies_images_but_points_pdf_pages():
    base = 0x2222
    items = [
        VisualItem("PG", "pdf_page", base, page=1, document_id="D001"),
        VisualItem("O2", "png", base, page=1, path="a.png"),
    ]
    plan = match.stage_plan(match.build_groups(items, threshold=2), "H:/Recovered")
    kinds = {p["action"] for p in plan}
    assert kinds == {"write_pointer", "copy"}          # pdf pointer, image copy
    assert not any(p.get("from", "").endswith(".pdf") for p in plan)   # deck never copied
    ptr = [p for p in plan if p["action"] == "write_pointer"][0]
    assert ptr["points_to"] == {"document": "D001", "page": 1}


def test_lone_image_is_not_a_group():
    assert match.build_groups([VisualItem("O1", "png", 0x1111, path="x.png")]) == []


def test_w9_and_d22_registered():
    r = registry.load()
    assert r.lookup("workflows", "W9") == "Cross-format visual slide recovery"
    assert r.decision("D22")["ruling"]["source"] == ".pdf"
