"""Plan lifting nested folders to a root without disassembling detected series.

This module is deliberately plan-only.  It never moves, renames, deletes, or
rewrites a source.  Nested folders are ordered deepest-first so a later reviewed
executor can lift every folder to the selected root while preserving its files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "david-os.series-aware-flatten-plan.v1"
_SERIES_FIELD = re.compile(r"(?im)^series\s*:\s*[\"']?([^\n\"']+)")
_NAMED_NUMBER = re.compile(
    r"(?i)\b(chapter|part|paper|law|book|volume|vol|section|step|phase|road)[-_ ]*(\d+(?:\.\d+)*)\b"
)
_LEADING_NUMBER = re.compile(r"^\s*(\d{1,4})(?:[._ -]+)(.+)$")
_CODED_NUMBER = re.compile(r"(?i)^\s*([A-Z]{1,8})[._ -]*(\d{1,4}(?:\.\d+)*)\b")
_EXPLICIT_SERIES = re.compile(r"(?i)(^|[_ -])(series|papers?|chapters?|roads?|laws?)([_ -]|$)")

_BLOCKED_NAMES = {
    ".git", ".obsidian", ".claude", ".stfolder", ".stversions",
    "node_modules", "__pycache__", "$recycle.bin", "#recycle",
    "system volume information",
}
_PROTECTED_WORDS = re.compile(r"(?i)(archive|backup|legacy|exclude|quarantine|recovery)")
_PROJECT_MARKERS = {".git", "package.json", "pyproject.toml", "cargo.toml", ".obsidian"}
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
_DOCUMENT_SUFFIXES = {".md", ".markdown", ".txt", ".doc", ".docx", ".pdf", ".html", ".htm", ".rtf"}


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


@dataclass(frozen=True)
class ClassificationRegistry:
    workbook: str
    workbook_sha256: str
    family_aliases: dict[str, str]
    package_aliases: dict[str, str]
    filename_series: dict[str, tuple[str, ...]]
    index_file: str = ""
    index_sha256: str = ""
    series_record_counts: dict[str, int] | None = None
    series_unique_filename_counts: dict[str, int] | None = None


def load_classification_registry(workbook: Path) -> ClassificationRegistry:
    """Read series/package identities from the master classification workbook."""
    import openpyxl

    workbook = workbook.resolve(strict=True)
    book = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    family_aliases: dict[str, str] = {}
    package_aliases: dict[str, str] = {}
    filename_values: dict[str, set[str]] = {}
    series_record_counts: Counter[str] = Counter()
    series_unique_filenames: dict[str, set[str]] = {}

    if "Series Families" in book.sheetnames:
        rows = book["Series Families"].iter_rows(values_only=True)
        next(rows, None)
        for code, series, *_rest in rows:
            canonical = str(series or code or "").strip()
            if not canonical:
                continue
            for alias in (code, series):
                key = _norm(alias)
                if key:
                    family_aliases[key] = canonical

    if "Organized Intake" in book.sheetnames:
        rows = book["Organized Intake"].iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(rows, ())]
        positions = {name: index for index, name in enumerate(headers)}
        for row in rows:
            kind = str(row[positions.get("Kind", -1)] or "") if "Kind" in positions else ""
            if "folder" not in kind.casefold() and "package" not in kind.casefold():
                continue
            source = row[positions["Source item"]] if "Source item" in positions else None
            code = row[positions["Short code"]] if "Short code" in positions else None
            canonical = str(code or source or "").strip()
            for alias in (source, code):
                key = _norm(alias)
                if key:
                    package_aliases[key] = canonical

    if "Full Vault Index" in book.sheetnames:
        rows = book["Full Vault Index"].iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(rows, ())]
        positions = {name: index for index, name in enumerate(headers)}
        if "series" in positions and "file_path" in positions:
            for row in rows:
                series = str(row[positions["series"]] or "").strip()
                raw_path = str(row[positions["file_path"]] or "").strip()
                if not series or not raw_path:
                    continue
                filename_values.setdefault(Path(raw_path).name.casefold(), set()).add(series)
                series_record_counts[series] += 1
                series_unique_filenames.setdefault(series, set()).add(Path(raw_path).name.casefold())

    filename_series = {
        name: tuple(sorted(values)) for name, values in filename_values.items()
    }
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
    return ClassificationRegistry(
        workbook=str(workbook),
        workbook_sha256=digest,
        family_aliases=family_aliases,
        package_aliases=package_aliases,
        filename_series=filename_series,
        series_record_counts=dict(series_record_counts),
        series_unique_filename_counts={key: len(values) for key, values in series_unique_filenames.items()},
    )


def add_classification_index(
    registry: ClassificationRegistry, index_file: Path
) -> ClassificationRegistry:
    """Overlay a tab-delimited Full Vault Index export on the workbook registry."""
    index_file = index_file.resolve(strict=True)
    combined = {name: set(values) for name, values in registry.filename_series.items()}
    series_record_counts: Counter[str] = Counter()
    series_unique_filenames: dict[str, set[str]] = {}
    with index_file.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"series", "file_path"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("classification index requires tab-delimited series and file_path columns")
        for row in reader:
            series = str(row.get("series") or "").strip()
            raw_path = str(row.get("file_path") or "").strip()
            if series and raw_path:
                combined.setdefault(Path(raw_path).name.casefold(), set()).add(series)
                series_record_counts[series] += 1
                series_unique_filenames.setdefault(series, set()).add(Path(raw_path).name.casefold())
    return ClassificationRegistry(
        workbook=registry.workbook,
        workbook_sha256=registry.workbook_sha256,
        family_aliases=registry.family_aliases,
        package_aliases=registry.package_aliases,
        filename_series={name: tuple(sorted(values)) for name, values in combined.items()},
        index_file=str(index_file),
        index_sha256=hashlib.sha256(index_file.read_bytes()).hexdigest(),
        series_record_counts=dict(series_record_counts) or registry.series_record_counts,
        series_unique_filename_counts=(
            {key: len(values) for key, values in series_unique_filenames.items()}
            or registry.series_unique_filename_counts
        ),
    )


@dataclass(frozen=True)
class FolderDecision:
    sequence: int
    depth: int
    source: str
    destination: str
    action: str
    series_key: str
    evidence: str
    collision: bool
    direct_file_count: int
    recursive_file_count: int
    recursive_document_count: int
    matched_classification_count: int
    registry_series_record_count: int
    registry_unique_filename_count: int
    mutation_authorized: bool = False


def _depth(root: Path, folder: Path) -> int:
    return len(folder.relative_to(root).parts)


def _safe_walk(root: Path):
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        dirs[:] = [
            name for name in dirs
            if name.casefold() not in _BLOCKED_NAMES
            and not (here / name).is_symlink()
            and not getattr(here / name, "is_junction", lambda: False)()
        ]
        yield here, dirs, files


def _project_or_archive(folder: Path) -> str | None:
    if _PROTECTED_WORDS.search(folder.name):
        return "archive/recovery name"
    try:
        names = {p.name.casefold() for p in folder.iterdir()}
    except OSError:
        return "unreadable folder"
    markers = sorted(marker for marker in _PROJECT_MARKERS if marker.casefold() in names)
    return f"project marker: {', '.join(markers)}" if markers else None


def _file_marker(path: Path) -> tuple[str, str] | None:
    stem = path.stem
    match = _NAMED_NUMBER.search(stem)
    if match:
        return f"named:{match.group(1).casefold()}", match.group(2)
    match = _CODED_NUMBER.search(stem)
    if match:
        return f"coded:{match.group(1).upper()}", match.group(2)
    match = _LEADING_NUMBER.match(stem)
    if match:
        return "leading-number", match.group(1)
    return None


def detect_series(
    folder: Path, registry: ClassificationRegistry | None = None
) -> tuple[str, list[str]] | None:
    try:
        files = [path for path in folder.iterdir() if path.is_file()]
    except OSError:
        return None
    evidence: list[str] = []
    if registry:
        folder_key = _norm(folder.name)
        package = registry.package_aliases.get(folder_key)
        if package:
            return package, ["master workbook Organized Intake package match"]
        family = registry.family_aliases.get(folder_key)
        if family:
            return family, ["master workbook Series Families name/code match"]

        workbook_matches: Counter[str] = Counter()
        ambiguous = 0
        for path in files:
            choices = registry.filename_series.get(path.name.casefold(), ())
            if len(choices) == 1:
                workbook_matches[choices[0]] += 1
            elif len(choices) > 1:
                ambiguous += 1
        if workbook_matches:
            key, count = workbook_matches.most_common(1)[0]
            other = sum(workbook_matches.values()) - count
            if count >= 2 and other == 0:
                note = f"{count} direct filenames map uniquely to workbook series={key}"
                if ambiguous:
                    note += f"; {ambiguous} ambiguous filename matches ignored"
                return key, [note]
    frontmatter: Counter[str] = Counter()
    markers: dict[str, set[str]] = {}
    for path in files:
        marker = _file_marker(path)
        if marker:
            markers.setdefault(marker[0], set()).add(marker[1])
        if path.suffix.casefold() in _TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:8_000]
            except OSError:
                continue
            match = _SERIES_FIELD.search(text)
            if match:
                frontmatter[match.group(1).strip()] += 1

    if frontmatter:
        key, count = frontmatter.most_common(1)[0]
        if count >= 2:
            evidence.append(f"{count} direct files declare series={key}")
            return key, evidence
    strongest = sorted(markers.items(), key=lambda item: (-len(item[1]), item[0]))
    if strongest and len(strongest[0][1]) >= 3:
        kind, positions = strongest[0]
        evidence.append(f"{kind} positions: {', '.join(sorted(positions))}")
        return kind, evidence
    if _EXPLICIT_SERIES.search(folder.name) and len(files) >= 2:
        evidence.append("folder name explicitly identifies a series")
        return folder.name, evidence
    return None


def _registry_series_total(
    registry: ClassificationRegistry | None, key: str, *, unique: bool = False
) -> int:
    if not registry or not key:
        return 0
    counts = registry.series_unique_filename_counts if unique else registry.series_record_counts
    if not counts:
        return 0
    if key in counts:
        return counts[key]
    wanted = _norm(key)
    for series, count in counts.items():
        if _norm(series) == wanted:
            return count
    aliases = {
        alias for alias, canonical in registry.family_aliases.items()
        if _norm(canonical) == wanted
    }
    return sum(count for series, count in counts.items() if _norm(series) in aliases)


def _folder_counts(
    folder: Path, registry: ClassificationRegistry | None, series_key: str
) -> tuple[int, int, int, int]:
    try:
        direct = sum(1 for path in folder.iterdir() if path.is_file())
    except OSError:
        direct = 0
    recursive = 0
    documents = 0
    matched = 0
    for _current, _dirs, files in _safe_walk(folder):
        for name in files:
            recursive += 1
            if Path(name).suffix.casefold() in _DOCUMENT_SUFFIXES:
                documents += 1
            if registry:
                choices = registry.filename_series.get(name.casefold(), ())
                if series_key:
                    if series_key in choices or any(_norm(value) == _norm(series_key) for value in choices):
                        matched += 1
                elif choices:
                    matched += 1
    return direct, recursive, documents, matched


def build_plan(root: Path, registry: ClassificationRegistry | None = None) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    folders: list[Path] = []
    protected: list[dict] = []
    series_roots: dict[Path, tuple[str, list[str]]] = {}
    for folder, dirs, _files in _safe_walk(root):
        if folder == root:
            continue
        protection = _project_or_archive(folder)
        if protection:
            protected.append({"path": str(folder), "reason": protection})
            dirs[:] = []
            continue
        detected = detect_series(folder, registry)
        if detected:
            series_roots[folder] = detected
            dirs[:] = []
        folders.append(folder)

    rows: list[FolderDecision] = []
    occupied = {child.name.casefold(): child for child in root.iterdir()}
    ordered = sorted(folders, key=lambda path: (-_depth(root, path), str(path).casefold()))
    for sequence, folder in enumerate(ordered, 1):
        depth = _depth(root, folder)
        if depth <= 1:
            continue
        target = root / folder.name
        existing = occupied.get(folder.name.casefold())
        collision = existing is not None and existing.resolve() != folder.resolve()
        detected = series_roots.get(folder)
        action = "HOLD_COLLISION" if collision else "LIFT_SERIES_FOLDER" if detected else "LIFT_FOLDER"
        key = detected[0] if detected else ""
        evidence = "; ".join(detected[1]) if detected else "nested folder; preserve contents as one unit"
        direct, recursive, documents, matched = _folder_counts(folder, registry, key)
        rows.append(FolderDecision(
            sequence, depth, str(folder), str(target), action, key, evidence, collision,
            direct, recursive, documents, matched,
            _registry_series_total(registry, key),
            _registry_series_total(registry, key, unique=True),
        ))
        if not collision:
            occupied[folder.name.casefold()] = folder

    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "mode": "DRY_RUN_PLAN_ONLY",
        "source_mutations": False,
        "classification_workbook": (
            {"path": registry.workbook, "sha256": registry.workbook_sha256}
            if registry else None
        ),
        "classification_index": (
            {"path": registry.index_file, "sha256": registry.index_sha256}
            if registry and registry.index_file else None
        ),
        "decisions": [asdict(row) for row in rows],
        "protected": protected,
        "counts": {
            "lift_folder": sum(row.action == "LIFT_FOLDER" for row in rows),
            "lift_series_folder": sum(row.action == "LIFT_SERIES_FOLDER" for row in rows),
            "hold_collision": sum(row.action == "HOLD_COLLISION" for row in rows),
            "protected": len(protected),
        },
    }


def write_plan(plan: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
    (output / "plan.json").write_text(payload, encoding="utf-8")
    decisions = plan["decisions"]
    with (output / "plan.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = list(decisions[0]) if decisions else ["sequence", "source", "destination", "action"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(decisions)
    receipt = {
        "schema": SCHEMA,
        "root": plan["root"],
        "source_mutations": False,
        "plan_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "counts": plan["counts"],
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--classification-workbook", type=Path)
    parser.add_argument("--classification-index", type=Path)
    args = parser.parse_args()
    registry = (
        load_classification_registry(args.classification_workbook)
        if args.classification_workbook else None
    )
    if args.classification_index:
        if registry is None:
            raise ValueError("--classification-index requires --classification-workbook")
        registry = add_classification_index(registry, args.classification_index)
    plan = build_plan(args.root, registry)
    write_plan(plan, args.output)
    print(json.dumps(plan["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
