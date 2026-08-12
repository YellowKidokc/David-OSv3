import tempfile
from pathlib import Path

import pytest

from fis import visual, match

PIL = visual.available()
pytestmark = pytest.mark.skipif(not PIL, reason="Pillow not installed")


def _make(dirpath):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 360, 120], fill="navy")
    d.ellipse([120, 150, 280, 270], fill="orange")
    p = Path(dirpath)
    img.save(p / "slide.png")
    img.save(p / "slide.webp", quality=60)     # lossy conversion, different bytes
    img.save(p / "deck.pdf", "PDF")
    Image.new("RGB", (400, 300), "black").save(p / "unrelated.png")
    return p


def test_png_and_webp_of_same_image_hash_close():
    p = _make(tempfile.mkdtemp())
    hp = visual.phash_image(str(p / "slide.png"))
    hw = visual.phash_image(str(p / "slide.webp"))
    assert visual.hamming(hp, hw) <= 4          # same picture across formats
    ho = visual.phash_image(str(p / "unrelated.png"))
    assert visual.hamming(hp, ho) > 10          # different picture


def test_pdf_page_matches_its_image_and_groups_cross_format():
    p = _make(tempfile.mkdtemp())
    items = []
    for f, rep in [("slide.png", "png"), ("slide.webp", "webp")]:
        items.append(match.VisualItem(object_id=f, representation=rep,
                                      phash=visual.phash_image(str(p / f)), path=str(p / f)))
    for i, h in enumerate(visual.phash_pdf_pages(str(p / "deck.pdf")), start=1):
        items.append(match.VisualItem(object_id=f"D000-p{i}", representation="pdf_page",
                                      phash=h, page=i, document_id="D000"))
    groups = match.build_groups(items, threshold=6)
    assert len(groups) == 1                      # png + webp + pdf_page = one family
    reps = {m.representation for m in groups[0].members}
    assert reps == {"png", "webp", "pdf_page"}
