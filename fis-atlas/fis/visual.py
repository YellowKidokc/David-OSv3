"""# fis-op: idn
Perceptual hashing — the SECOND identity. "Same picture" across formats.

Content hash (BLAKE3/SHA) proves exact bytes. Perceptual hash proves a PNG, its
WebP conversion, and a rendered PDF page are the SAME image. Deterministic and
re-verifiable from the ledger — a vision model's answer is not, so the model
only adjudicates the ambiguous band and its verdict is 'inferred', never auto-acted.

dHash: 9x8 grayscale, compare adjacent pixels -> 64 bits. The math (dhash_from_gray,
hamming) is pure and testable. Decoding PNG/WebP needs Pillow; PDF pages need
PyMuPDF — both optional; absence degrades to 'no perceptual hash', never a crash.
"""
from __future__ import annotations

DHASH_SIDE = 8          # 9x8 -> 64 bits


def dhash_from_gray(gray: list[int], w: int, h: int) -> int:
    """gray: row-major grayscale of size w x h (w == side+1, h == side). Pure."""
    bits = 0
    for row in range(h):
        for col in range(w - 1):
            left = gray[row * w + col]
            right = gray[row * w + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def is_same_picture(a: int, b: int, threshold: int = 10) -> bool:
    """Under-merge on purpose: slide decks share template chrome, so a tight
    threshold proposes candidates; a family is only DECLARED after confirmation."""
    return hamming(a, b) <= threshold


# ---- optional real backends (guarded) -------------------------------------
def available() -> bool:
    try:
        import PIL  # noqa
        return True
    except Exception:
        return False


def phash_image(path: str) -> int | None:
    """Perceptual hash of a PNG/WebP/JPEG via Pillow. None if Pillow absent."""
    try:
        from PIL import Image
        img = Image.open(path).convert("L").resize((DHASH_SIDE + 1, DHASH_SIDE))
        gray = list(img.getdata())
        return dhash_from_gray(gray, DHASH_SIDE + 1, DHASH_SIDE)
    except Exception:
        return None


def phash_pdf_pages(path: str, max_pages: int = 60) -> list[int]:
    """Render each PDF page and perceptual-hash it (PyMuPDF). [] if unavailable."""
    out = []
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        doc = fitz.open(path)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3))
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img = img.convert("L").resize((DHASH_SIDE + 1, DHASH_SIDE))
            out.append(dhash_from_gray(list(img.getdata()), DHASH_SIDE + 1, DHASH_SIDE))
    except Exception:
        return out
    return out
