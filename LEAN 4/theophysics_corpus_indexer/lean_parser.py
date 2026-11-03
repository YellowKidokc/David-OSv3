"""Lean 4 lexical helpers: mask comments/strings, extract declarations/imports, count active sorry."""

from __future__ import annotations

import re

# Match top-level declaration introducers.
DECL_RE = re.compile(
    r"^\s*(?:theorem|lemma|def|axiom|instance|structure|class|inductive)\s+"
    r"([^\s(:[{]+)",
    re.MULTILINE,
)

IMPORT_RE = re.compile(r"^\s*import\s+([^\n]+)", re.MULTILINE)

# Namespace and section names are content-derived keywords too.
NAMESPACE_RE = re.compile(r"^\s*namespace\s+([\w.]+)", re.MULTILINE)
SECTION_RE = re.compile(r"^\s*section\s+([\w.]+)", re.MULTILINE)

# Match a bare 'sorry' token.
SORRY_RE = re.compile(r"\bsorry\b")


def mask_comments_and_strings(code: str) -> str:
    """Remove Lean strings and comments so keyword matching stays in live code."""
    # Block comments /-
    code = re.sub(r"/-[\s\S]*?-/", " ", code)
    # Line comments --
    code = re.sub(r"--[^\n]*", " ", code)
    # Strings (non-greedy, does not handle escaped quotes)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', " ", code)
    return code


def parse_declarations(code: str) -> list[tuple[str, str]]:
    """Return (kind, name) tuples for top-level declarations."""
    masked = mask_comments_and_strings(code)
    decls: list[tuple[str, str]] = []
    for m in DECL_RE.finditer(masked):
        full = m.group(0).strip()
        # Determine kind from the leading keyword.
        kind = full.split()[0]
        name = m.group(1).strip()
        decls.append((kind, name))
    return decls


def extract_namespaces(code: str) -> list[str]:
    """Return namespace and section names introduced in the file."""
    masked = mask_comments_and_strings(code)
    names: list[str] = []
    for m in NAMESPACE_RE.finditer(masked):
        names.append(m.group(1))
    for m in SECTION_RE.finditer(masked):
        names.append(m.group(1))
    return names


def extract_imports(code: str) -> list[str]:
    """Return module names imported by the file."""
    masked = mask_comments_and_strings(code)
    imports: list[str] = []
    for m in IMPORT_RE.finditer(masked):
        parts = m.group(1).split()
        # Handle "import Foo.Bar" and "import Foo.Bar as Baz"
        if parts:
            imports.append(parts[0])
    return imports


def count_active_sorry(code: str) -> int:
    """Count 'sorry' occurrences outside comments and strings."""
    masked = mask_comments_and_strings(code)
    return len(SORRY_RE.findall(masked))


def count_theorem_lemma_def(decls: list[tuple[str, str]]) -> int:
    """Lexical count of theorem/lemma/def declarations."""
    return sum(1 for kind, _ in decls if kind in ("theorem", "lemma", "def"))
