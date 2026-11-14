#!/usr/bin/env python3
"""Canon Guard: version-aware canonical document drift detection and safe repair.

Standard-library only. Python 3.11+ is recommended (tomllib).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TOOL_VERSION = "0.1.0"
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".tex", ".lean", ".rst"}
EQUATION_FENCE = re.compile(r"```(?:math|latex|tex)?\s*\n(.*?)```", re.S | re.I)
DISPLAY_MATH = re.compile(r"\$\$(.*?)\$\$|\\\[(.*?)\\\]", re.S)
VERSION_PATTERNS = (
    re.compile(r"(?im)^\s*(?:version|canonical_version)\s*:\s*[\"']?([vV]?\d+(?:\.\d+){0,2})"),
    re.compile(r"(?i)\b(?:version|v)\s*([0-9]+(?:\.[0-9]+){1,2})\b"),
)
DATE_PATTERNS = (
    re.compile(r"(?im)^\s*(?:effective_date|canonical_date|date)\s*:\s*[\"']?(\d{4}-\d{2}-\d{2})"),
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
)
CANON_MARKERS = re.compile(r"(?i)(#canon\b|status\s*:\s*canon|canonical reference|source of truth)")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_equation(value: str) -> str:
    replacements = {
        "χ": "chi", "Χ": "chi", "·": "*", "×": "*", "∭": "triple_integral",
        "∫": "integral", "−": "-", "–": "-", "—": "-", "²": "^2", "³": "^3",
        "μ": "mu", "ν": "nu", "∂": "partial", "≥": ">=", "≤": "<=", "→": "->",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\\(?:left|right|,|;|!|quad|qquad)\b", "", value)
    value = re.sub(r"\\cdot|\\times", "*", value)
    value = re.sub(r"\\chi\b", "chi", value)
    value = re.sub(r"\\(?:mathrm|text)\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\s+", "", value)
    return value.casefold()


def parse_version(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    raw = value.lower().lstrip("v")
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", raw):
        return None
    parts = [int(x) for x in raw.split(".")]
    return tuple((parts + [0, 0])[:3])  # type: ignore[return-value]


@dataclasses.dataclass(frozen=True)
class Equation:
    raw: str
    normalized: str
    line: int
    fingerprint: str


@dataclasses.dataclass
class Document:
    path: Path
    relative_path: str
    text: str
    fingerprint: str
    title: str | None
    declared_version: str | None
    parsed_version: tuple[int, int, int] | None
    declared_date: str | None
    canon_marked: bool
    equations: list[Equation]


@dataclasses.dataclass
class Finding:
    code: str
    severity: str
    path: str
    message: str
    line: int | None = None
    canonical_id: str | None = None
    repairable: bool = False
    proposed_replacement: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


MATH_OPERATORS = set("+-*/^·×∂∇∆ΓΨχ∭∫∑∏∈∀∃→⟹≈≠≤≥∝∞¬∧∨⊕⊗⊙⊘⌢≔≕≡≅≃")
LEAN_STARTS = (
    "have ", "by ", "rfl", "id", "import ", "open ", "namespace ", "theorem ",
    "lemma ", "def ", "example ", "inductive ", "structure ", "class ",
    "instance ", "variable", "universe ", "axiom ", "opaque ", "partial ",
    "private ", "protected ", "show ", "let ", "where ", "mutual ",
)


def is_plausible_equation(raw: str) -> bool:
    """Heuristic filter to drop prose, glyph directives, Lean code, HTML, and tables."""
    s = raw.strip()
    if len(s) < 3 or len(s) > 200:
        return False
    if s.startswith(("::glyph", "|", "# ", "## ", "### ")):
        return False
    if ":=" in s or s.endswith(":="):
        return False
    if "http" in s or "www." in s:
        return False
    if any(s.startswith(kw) for kw in LEAN_STARTS):
        return False
    # Drop HTML fragments (e.g., radio button labels).
    if re.search(r"<\s*(label|input|div|span|button)[\s>]", s, re.I):
        return False
    if "=" not in s:
        return False
    # Require at least one operator beyond plain assignment.
    if not any(op in s for op in MATH_OPERATORS):
        return False
    # Reject prose-heavy lines (e.g., long sentences that happen to contain '=').
    if len(s.split()) > 12:
        return False
    # Reject lines that are mostly explanatory English around a single relation.
    english_word_count = len(re.findall(r"[a-zA-Z]{2,}", s))
    if english_word_count > 4:
        return False
    return True


def extract_equations(text: str, strict: bool = False) -> list[Equation]:
    found: list[Equation] = []
    matches = list(EQUATION_FENCE.finditer(text)) + list(DISPLAY_MATH.finditer(text))
    for match in sorted(matches, key=lambda m: m.start()):
        raw = next((g for g in match.groups() if g is not None), match.group(0)).strip()
        if not any(ch in raw for ch in "=≥≤∫χ\\"):
            continue
        if strict and not is_plausible_equation(raw):
            continue
        normalized = normalize_equation(raw)
        found.append(Equation(raw, normalized, text.count("\n", 0, match.start()) + 1,
                              sha256_text(normalized)))
    # Equation-like lines in plain/code blocks.
    occupied = [(m.start(), m.end()) for m in matches]
    offset = 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        is_occupied = any(start <= offset < end for start, end in occupied)
        stripped = line.strip().strip("`")
        if (not is_occupied and "=" in stripped and 3 < len(stripped) < 500
                and not stripped.startswith(("|", "#", "-", "*", "<"))
                and re.search(r"[A-Za-zχ∂∇ΓΨ]|\\", stripped)):
            if strict and not is_plausible_equation(stripped):
                continue
            normalized = normalize_equation(stripped)
            found.append(Equation(stripped, normalized, number, sha256_text(normalized)))
        offset += len(line)
    unique: dict[tuple[int, str], Equation] = {(e.line, e.fingerprint): e for e in found}
    return sorted(unique.values(), key=lambda e: e.line)


def parse_document(path: Path, root: Path) -> Document:
    text = path.read_text(encoding="utf-8", errors="replace")
    title_match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    version = next((m.group(1) for pattern in VERSION_PATTERNS if (m := pattern.search(text))), None)
    date = next((m.group(1) for pattern in DATE_PATTERNS if (m := pattern.search(text))), None)
    return Document(
        path=path,
        relative_path=path.relative_to(root).as_posix(),
        text=text,
        fingerprint=sha256_text(text),
        title=title_match.group(1).strip() if title_match else None,
        declared_version=version,
        parsed_version=parse_version(version),
        declared_date=date,
        canon_marked=bool(CANON_MARKERS.search(text[:5000])),
        equations=extract_equations(text),
    )


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("manifest", {}).get("schema") != 1:
        raise ValueError("manifest.schema must equal 1")
    ids: set[str] = set()
    for item in data.get("documents", []):
        doc_id = item.get("id")
        if not doc_id or doc_id in ids:
            raise ValueError(f"document id missing or duplicated: {doc_id!r}")
        ids.add(doc_id)
        if parse_version(str(item.get("version", ""))) is None:
            raise ValueError(f"invalid semantic version for {doc_id}")
    return data


def iter_text_files(root: Path, excludes: Iterable[str]) -> Iterable[Path]:
    excluded = {Path(x).as_posix().rstrip("/") for x in excludes}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if any(rel == item or rel.startswith(item + "/") for item in excluded):
            continue
        yield path


def resolve_canonical_documents(manifest: dict[str, Any], root: Path) -> tuple[dict[str, Document], list[Finding]]:
    resolved: dict[str, Document] = {}
    findings: list[Finding] = []
    for spec in manifest.get("documents", []):
        rel = str(spec["path"])
        path = root / rel
        if not path.is_file():
            findings.append(Finding("CANON_MISSING", "error", rel,
                                    f"Canonical document {spec['id']} is missing.",
                                    canonical_id=spec["id"]))
            continue
        doc = parse_document(path, root)
        expected_hash = str(spec.get("sha256", "")).strip()
        if expected_hash and expected_hash != doc.fingerprint:
            findings.append(Finding("CANON_TAMPERED", "critical", rel,
                                    "Canonical file hash differs from the manifest.",
                                    canonical_id=spec["id"]))
        resolved[spec["id"]] = doc
    return resolved, findings


def check_version_metadata(doc: Document, spec: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    expected = str(spec["version"])
    if doc.parsed_version is None:
        out.append(Finding("VERSION_MISSING", "warning", doc.relative_path,
                           f"Canonical document declares no machine-readable version; manifest says {expected}.",
                           canonical_id=spec["id"]))
    elif doc.parsed_version != parse_version(expected):
        out.append(Finding("VERSION_CONFLICT", "error", doc.relative_path,
                           f"Document says {doc.declared_version}; authority manifest says {expected}.",
                           canonical_id=spec["id"]))
    return out


def compile_rule(rule: dict[str, Any]) -> re.Pattern[str]:
    flags = re.MULTILINE
    if not rule.get("case_sensitive", False):
        flags |= re.IGNORECASE
    return re.compile(str(rule["pattern"]), flags)


def apply_claim_rules(doc: Document, manifest: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for rule in manifest.get("claims", []):
        scope = rule.get("scope", ["**"])
        if not any(item == "**" or Path(doc.relative_path).match(item) for item in scope):
            continue
        exclude_scope = rule.get("exclude_scope", [])
        if any(Path(doc.relative_path).match(item) for item in exclude_scope):
            continue
        pattern = compile_rule(rule)
        matches = list(pattern.finditer(doc.text))
        mode = rule.get("mode", "forbid")
        if mode == "require" and not matches:
            findings.append(Finding(str(rule["id"]), str(rule.get("severity", "error")),
                                    doc.relative_path, str(rule["message"]),
                                    canonical_id=rule.get("canonical_id")))
        elif mode == "forbid":
            for match in matches:
                findings.append(Finding(
                    str(rule["id"]), str(rule.get("severity", "error")), doc.relative_path,
                    str(rule["message"]), doc.text.count("\n", 0, match.start()) + 1,
                    rule.get("canonical_id"), bool(rule.get("safe_fix", False)),
                    rule.get("replacement"),
                ))
    return findings


def compare_equations(doc: Document, manifest: dict[str, Any], canonical: dict[str, Document]) -> list[Finding]:
    findings: list[Finding] = []
    if any(doc.path == item.path for item in canonical.values()):
        return findings
    canonical_equations: dict[str, tuple[str, Equation]] = {}
    for canon_id, canon_doc in canonical.items():
        for equation in canon_doc.equations:
            canonical_equations[equation.fingerprint] = (canon_id, equation)
    aliases = manifest.get("equation_aliases", [])
    alias_patterns = []
    for a in aliases:
        allowed = {normalize_equation(str(a["canonical"]))}
        for view in a.get("views", []):
            allowed.add(normalize_equation(str(view["canonical"])))
        alias_patterns.append((re.compile(str(a["detect"]), re.I), allowed, a))
    for equation in doc.equations:
        if equation.fingerprint in canonical_equations:
            continue
        for detect, allowed, alias in alias_patterns:
            if detect.search(equation.raw) and equation.normalized not in allowed:
                findings.append(Finding(
                    str(alias["id"]), str(alias.get("severity", "error")), doc.relative_path,
                    str(alias["message"]), equation.line, alias.get("canonical_id"),
                    bool(alias.get("safe_fix", False)), alias.get("replacement"),
                ))
                break
    return findings


def check_false_canon(doc: Document, manifest_paths: set[str]) -> list[Finding]:
    if doc.canon_marked and doc.relative_path not in manifest_paths:
        return [Finding("UNREGISTERED_CANON", "error", doc.relative_path,
                        "Document claims canonical authority but is not registered in the authority manifest.")]
    return []


def repair_document(doc: Document, findings: list[Finding], backup_root: Path,
                    allow_codes: set[str]) -> tuple[bool, str]:
    applicable = [f for f in findings if f.repairable and f.proposed_replacement is not None
                  and (not allow_codes or f.code in allow_codes)]
    if not applicable:
        return False, ""
    updated = doc.text
    for finding in applicable:
        # Repairs are rule-based and bounded. Never rewrite an equation via approximate matching.
        updated = re.sub(
            next(f["pattern"] for f in CURRENT_MANIFEST.get("claims", []) if f["id"] == finding.code),
            finding.proposed_replacement or "", updated,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    if updated == doc.text:
        return False, ""
    backup = backup_root / doc.relative_path
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(doc.path, backup)
    diff = "".join(difflib.unified_diff(
        doc.text.splitlines(keepends=True), updated.splitlines(keepends=True),
        fromfile=doc.relative_path, tofile=doc.relative_path,
    ))
    fd, temp_name = tempfile.mkstemp(prefix=".canon-guard-", dir=doc.path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, doc.path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return True, diff


def make_review_packet(root: Path, documents: list[Document], findings: list[Finding],
                       output: Path) -> None:
    payload = {
        "schema": 1,
        "tool_version": TOOL_VERSION,
        "instruction": (
            "Classify each finding as contradiction, compatible restatement, version mismatch, "
            "or insufficient evidence. Quote exact evidence. Never modify canon. Return JSON only."
        ),
        "documents": [{
            "path": d.relative_path, "title": d.title, "version": d.declared_version,
            "date": d.declared_date, "canon_marked": d.canon_marked,
            "equations": [dataclasses.asdict(e) for e in d.equations],
        } for d in documents],
        "findings": [f.as_dict() for f in findings],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


CURRENT_MANIFEST: dict[str, Any] = {}


def run(args: argparse.Namespace) -> int:
    global CURRENT_MANIFEST
    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest).resolve()
    CURRENT_MANIFEST = load_manifest(manifest_path)
    canonical, findings = resolve_canonical_documents(CURRENT_MANIFEST, root)
    specs = {str(item["id"]): item for item in CURRENT_MANIFEST.get("documents", [])}
    for canon_id, doc in canonical.items():
        findings.extend(check_version_metadata(doc, specs[canon_id]))
    documents = [parse_document(p, root) for p in iter_text_files(
        root, CURRENT_MANIFEST.get("manifest", {}).get("exclude", []))]
    manifest_paths = {str(x["path"]) for x in CURRENT_MANIFEST.get("documents", [])}
    for doc in documents:
        findings.extend(check_false_canon(doc, manifest_paths))
        findings.extend(apply_claim_rules(doc, CURRENT_MANIFEST))
        findings.extend(compare_equations(doc, CURRENT_MANIFEST, canonical))
    findings.sort(key=lambda f: (f.path, f.line or 0, f.code))

    changed: list[str] = []
    diffs: list[str] = []
    if args.fix:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = root / ".canon-guard" / "backups" / stamp
        allowed = set(args.allow_fix or [])
        by_path: dict[str, list[Finding]] = {}
        for finding in findings:
            by_path.setdefault(finding.path, []).append(finding)
        for doc in documents:
            did_change, diff = repair_document(doc, by_path.get(doc.relative_path, []),
                                               backup_root, allowed)
            if did_change:
                changed.append(doc.relative_path)
                diffs.append(diff)

    report = {
        "schema": 1,
        "tool_version": TOOL_VERSION,
        "root": str(root),
        "canonical_documents": {
            key: {"path": value.relative_path, "sha256": value.fingerprint,
                  "detected_version": value.declared_version}
            for key, value in canonical.items()
        },
        "summary": {
            "files_scanned": len(documents), "findings": len(findings),
            "critical": sum(f.severity == "critical" for f in findings),
            "errors": sum(f.severity == "error" for f in findings),
            "warnings": sum(f.severity == "warning" for f in findings),
            "changed": len(changed),
        },
        "changed_files": changed,
        "findings": [f.as_dict() for f in findings],
    }
    if args.review_packet:
        make_review_packet(root, documents, findings, Path(args.review_packet))
    if args.format == "json":
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
    else:
        lines = [f"Canon Guard {TOOL_VERSION}: {len(documents)} files, {len(findings)} findings"]
        for f in findings:
            location = f"{f.path}:{f.line}" if f.line else f.path
            fix = " [safe-fix]" if f.repairable else ""
            lines.append(f"{f.severity.upper():8} {f.code:24} {location} — {f.message}{fix}")
        if changed:
            lines.append(f"Changed: {', '.join(changed)}")
        rendered = "\n".join(lines)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.show_diff and diffs:
        print("\n".join(diffs))
    return 2 if any(f.severity in {"critical", "error"} for f in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect canonical-version drift and perform explicitly safe repairs.")
    parser.add_argument("root", nargs="?", default=".", help="Tree to scan")
    parser.add_argument("-m", "--manifest", default="canon-manifest.toml")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("-o", "--output")
    parser.add_argument("--fix", action="store_true",
                        help="Apply only rules marked safe_fix=true; writes timestamped backups")
    parser.add_argument("--allow-fix", action="append",
                        help="Limit fixes to a rule ID; repeatable")
    parser.add_argument("--show-diff", action="store_true")
    parser.add_argument("--review-packet",
                        help="Write bounded JSON for optional human/LLM semantic adjudication")
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    return parser


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"canon-guard: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
