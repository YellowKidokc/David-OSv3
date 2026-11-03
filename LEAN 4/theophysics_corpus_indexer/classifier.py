"""Content-derived series classifier."""

from __future__ import annotations

import os
import re
from typing import Iterable

from config import CLASS_RULES, LIBRARY_DECL_MARKERS
from lean_parser import extract_imports, extract_namespaces, parse_declarations


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").lower()


def _is_library(
    path: str,
    decls: list[tuple[str, str]],
    imports: list[str],
) -> bool:
    """Library detection is the only rule allowed to use imports/paths."""
    norm = _norm_path(path)
    if "mathlib" in norm.split("/"):
        return True
    for mod in imports:
        if mod.startswith("Mathlib."):
            return True
    for kind, name in decls:
        if name in LIBRARY_DECL_MARKERS:
            return True
    return False


def _first_content_summary(code: str) -> str:
    """One-line summary from the first non-empty line of text."""
    for line in code.splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return ""


def classify(
    path: str,
    ext: str,
    code: str,
) -> tuple[str | None, float, bool, int | None, int | None, list[tuple[str, str]], str]:
    """Classify a single file.

    Returns:
        (series, series_conf, is_library, decl_count, sorry_active, declarations, summary)
    """
    ext_lower = ext.lower()
    is_library = False
    decl_count: int | None = None
    sorry_active: int | None = None
    decls: list[tuple[str, str]] = []

    if ext_lower == ".lean":
        from lean_parser import count_active_sorry, count_theorem_lemma_def

        decls = parse_declarations(code)
        imports = extract_imports(code)
        decl_count = count_theorem_lemma_def(decls)
        sorry_active = count_active_sorry(code)
        is_library = _is_library(path, decls, imports)
        namespaces = extract_namespaces(code)
        keyword_text = (
            " ".join(name for _, name in decls)
            + " " + " ".join(imports)
            + " " + " ".join(namespaces)
        )
    else:
        imports = []
        # For non-lean, use a bounded slice of content for keyword classification.
        keyword_text = code[:8192]
        is_library = _is_library(path, [], imports)

    summary = _first_content_summary(code)

    if is_library:
        return "LIBRARY", 1.0, True, decl_count, sorry_active, decls, summary

    series: str | None = None
    text_to_search = keyword_text.lower()
    for label, pattern in CLASS_RULES:
        if re.search(pattern, text_to_search):
            series = label
            break

    confidence = 0.95 if series else 0.0
    return series, confidence, False, decl_count, sorry_active, decls, summary
