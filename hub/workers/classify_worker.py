"""Deterministic v1 file classifier using suffixes and lightweight signatures."""
from __future__ import annotations

import mimetypes
from pathlib import Path

from hub.workers.parsers import parse_file_metadata

CATEGORY_BY_SUFFIX = {
    ".txt": "text", ".md": "text", ".rst": "text", ".log": "text",
    ".py": "code", ".js": "code", ".ts": "code", ".html": "code", ".css": "code", ".json": "data",
    ".csv": "data", ".xml": "data", ".yaml": "data", ".yml": "data", ".sql": "data",
    ".pdf": "document", ".doc": "document", ".docx": "document", ".rtf": "document", ".xlsx": "document",
    ".jpg": "media", ".jpeg": "media", ".png": "media", ".gif": "media", ".mp3": "media", ".mp4": "media",
    ".zip": "archive", ".gz": "archive", ".tar": "archive", ".7z": "archive", ".rar": "archive",
}

SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF-", "document", "pdf_signature"),
    (b"PK\x03\x04", "archive", "zip_signature"),
    (b"\x89PNG\r\n\x1a\n", "media", "png_signature"),
    (b"\xff\xd8\xff", "media", "jpeg_signature"),
    (b"GIF87a", "media", "gif_signature"),
    (b"GIF89a", "media", "gif_signature"),
    (b"\x1f\x8b", "archive", "gzip_signature"),
]

CODE_MARKERS = (b"#!/usr/bin/env", b"#!/bin/", b"import ", b"def ", b"function ", b"const ", b"class ")


def _read_head(path: Path, size: int = 4096) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def _looks_textual(head: bytes) -> bool:
    if not head:
        return False
    if b"\x00" in head:
        return False
    printable = sum(1 for byte in head if byte in b"\n\r\t" or 32 <= byte <= 126)
    return printable / max(len(head), 1) > 0.85


def classify_file(path: str, hash_result: dict[str, object] | None = None) -> dict[str, object]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    head = _read_head(file_path)
    mime_type, _ = mimetypes.guess_type(str(file_path))
    parser_result = parse_file_metadata(str(file_path))

    for signature, category, reason in SIGNATURES:
        if head.startswith(signature):
            return _payload(file_path, category, suffix, 0.99, reason, mime_type, hash_result, parser_result)

    if suffix in CATEGORY_BY_SUFFIX:
        return _payload(file_path, CATEGORY_BY_SUFFIX[suffix], suffix, 0.9, "suffix", mime_type, hash_result, parser_result)

    if _looks_textual(head):
        category = "code" if any(marker in head for marker in CODE_MARKERS) else "text"
        return _payload(file_path, category, suffix, 0.75, "text_signature", mime_type, hash_result, parser_result)

    return _payload(file_path, "unknown", suffix, 0.4, "no_deterministic_match", mime_type, hash_result, parser_result)


def _payload(
    file_path: Path,
    category: str,
    suffix: str,
    confidence: float,
    reason: str,
    mime_type: str | None,
    hash_result: dict[str, object] | None,
    parser_result: dict[str, object],
) -> dict[str, object]:
    return {
        "path": str(file_path),
        "label": category,
        "category": category,
        "suffix": suffix,
        "mime_type": mime_type,
        "confidence": confidence,
        "reason": reason,
        "hash": hash_result,
        "parser": parser_result["parser"],
        "metadata": parser_result["metadata"],
    }
