from fis import visual, match, registry
from fis.match import VisualItem


def test_hamming_and_same_picture():
    assert visual.hamming(0b1010, 0b1000) == 1
    assert visual.is_same_picture(0xFFFF0000FFFF0000, 0xFFFF0000FFFF0001, threshold=2)
    assert not visual.is_same_picture(0x0, 0xFFFFFFFFFFFFFFFF, threshold=10)


def test_dhash_is_deterministic():
    gray = [i % 7 for i in range(9 * 8)]          # 9x8
    assert visual.dhash_from_gray(gray, 9, 8) == visual.dhash_from_gray(gray, 9, 8)


def test_same_picture_across_formats_groups_pdf_png_webp():
    base = 0xA1B2C3D4E5F60718
    items = [
        VisualItem("O1", "H:/deck.pdf", "pdf", base, page=1),
        VisualItem("O2", "D:/slide.png", "png", base ^ 0b11, page=1),        # tiny diff
        VisualItem("O3", "Z:/slide.webp", "webp", base ^ 0b101, page=1),     # tiny diff
        VisualItem("O4", "D:/unrelated.png", "png", 0x0F0F0F0F0F0F0F0F, page=1),
    ]
    fams = match.build_families(items, threshold=10)
    assert len(fams) == 1                          # the pdf/png/webp collapse to ONE family
    fam = fams[0]
    assert {m.fmt for m in fam.members} == {"pdf", "png", "webp"}
    assert "O4" not in {m.object_id for m in fam.members}   # unrelated stays out


def test_family_naming_is_projection():
    base = 0x1234567890ABCDEF
    items = [
        VisualItem("O1", "a.pdf", "pdf", base, page=1),
        VisualItem("O2", "a.png", "png", base, page=1),
        VisualItem("O3", "a.webp", "webp", base, page=1),
    ]
    fam = match.build_families(items, threshold=2)[0]
    names = fam.names()
    assert names["O1"].endswith("01P.pdf")
    assert names["O2"].endswith("01N.png")
    assert names["O3"].endswith("01W.webp")
    # the shared A### identifies the slide; the last letter is the representation
    assert all(n.startswith(fam.family_id + "-01") for n in names.values())
    # identity lives in the manifest, not the filename
    assert fam.manifest()["members"][0]["role"] in ("source", "render", "derivative")


def test_lone_image_is_not_a_family():
    items = [VisualItem("O1", "x.png", "png", 0x1111, page=1)]
    assert match.build_families(items) == []


def test_stage_plan_is_copy_preview_only():
    base = 0x2222
    items = [VisualItem("O1", "a.pdf", "pdf", base), VisualItem("O2", "a.png", "png", base)]
    plan = match.stage_plan(match.build_families(items, threshold=2), "H:/Recovered")
    assert all(p["action"] == "copy" for p in plan)          # never move on discovery
    assert all("/Matched/" in p["to"] for p in plan)


def test_w9_and_d22_registered():
    r = registry.load()
    assert r.lookup("workflows", "W9") == "Cross-format visual slide recovery"
    assert r.decision("D22")["ruling"]["source"] == ".pdf"
