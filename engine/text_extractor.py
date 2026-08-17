"""
text_extractor.py — pull readable text out of a file for classification.

Standard-library first. Plain text / markdown / code / json read directly; HTML
is stripped of tags; pdf and docx are read only if the optional libs are present,
otherwise they return "" (and the file is classified by extension + filename).
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional

_SCRIPT_STYLE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")
_TAG = re.compile(r"(?s)<[^>]+>")

_TEXT_EXTS = {
    ".md", ".txt", ".html", ".htm", ".css", ".js", ".ts", ".py", ".json",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".log", ".csv", ".bat", ".ps1",
    ".ahk", ".sh", ".rtf",
}


def _read_text(path: Path, limit: int) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(limit)


def _strip_html(raw: str) -> str:
    raw = _SCRIPT_STYLE.sub(" ", raw)
    raw = re.sub(r"(?is)</(p|div|section|article|li|h[1-6]|tr)>", "\n", raw)
    raw = _TAG.sub(" ", raw)
    return html.unescape(raw)


def extract_text(path: str, limit: int = 200_000) -> str:
    """Return readable text, or "" if unreadable. Never raises."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in (".html", ".htm"):
            return _strip_html(_read_text(p, limit))
        if ext in _TEXT_EXTS:
            return _read_text(p, limit)
        if ext == ".pdf":
            return _extract_pdf(p, limit)
        if ext in (".docx",):
            return _extract_docx(p, limit)
    except Exception:
        return ""
    return ""


def _extract_pdf(p: Path, limit: int) -> str:
    try:
        from pypdf import PdfReader  # optional
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return ""
    try:
        reader = PdfReader(str(p))
        out = []
        for page in reader.pages:
            out.append(page.extract_text() or "")
            if sum(len(x) for x in out) > limit:
                break
        return "\n".join(out)[:limit]
    except Exception:
        return ""


def _extract_docx(p: Path, limit: int) -> str:
    try:
        import docx  # optional (python-docx)
    except Exception:
        return ""
    try:
        d = docx.Document(str(p))
        return "\n".join(par.text for par in d.paragraphs)[:limit]
    except Exception:
        return ""
