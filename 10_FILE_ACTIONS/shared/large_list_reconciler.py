"""Reconcile a large filename list with one or more filesystem roots.

Inputs: .xlsx, .csv, .tsv, or plain-text folder listings. Output is a JSON or
CSV review plan. This program is deliberately read-only: it cannot move, copy,
delete, rename, or merge files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


NAME_COLUMNS = ("filename", "file_name", "name", "file", "title")
PATH_COLUMNS = ("path", "full_path", "filepath", "relative_path", "source")
SIZE_COLUMNS = ("size", "bytes", "file_size")
BLOCKED_NAMES = {"$recycle.bin", "#recycle", "system volume information", ".git", "node_modules"}


@dataclass
class WantedFile:
    row: int
    name: str
    source_path: str = ""
    size: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Candidate:
    path: str
    name: str
    size: int
    modified_ns: int


def _normalized_headers(row: dict) -> dict[str, object]:
    return {str(key).strip().casefold(): value for key, value in row.items() if key is not None}


def _first(row: dict, choices: Iterable[str]):
    return next((row[key] for key in choices if key in row and row[key] not in (None, "")), None)


def _rows_from_xlsx(path: Path, sheet: str | None) -> list[dict]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Excel input requires openpyxl; CSV and text inputs need no extra package") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook[sheet] if sheet else workbook.active
    rows = worksheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]
    return [dict(zip(headers, values)) for values in rows]


def load_wanted(path: Path, sheet: str | None = None) -> list[WantedFile]:
    suffix = path.suffix.casefold()
    if suffix == ".xlsx":
        raw_rows = _rows_from_xlsx(path, sheet)
    elif suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
            raw_rows = list(csv.DictReader(stream, delimiter=delimiter))
    else:
        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            raw_rows = [{"filename": line.strip()} for line in stream if line.strip()]

    wanted: list[WantedFile] = []
    for number, raw in enumerate(raw_rows, start=2 if suffix in {".xlsx", ".csv", ".tsv"} else 1):
        row = _normalized_headers(raw)
        raw_path = str(_first(row, PATH_COLUMNS) or "").strip()
        raw_name = str(_first(row, NAME_COLUMNS) or "").strip()
        name = raw_name or (Path(raw_path).name if raw_path else "")
        if not name:
            continue
        size_value = _first(row, SIZE_COLUMNS)
        try:
            size = int(size_value) if size_value not in (None, "") else None
        except (TypeError, ValueError):
            size = None
        wanted.append(WantedFile(number, name, raw_path, size, dict(raw)))
    return wanted


def index_roots(roots: Iterable[Path]) -> tuple[dict[str, list[Candidate]], list[str]]:
    index: dict[str, list[Candidate]] = defaultdict(list)
    errors: list[str] = []

    def onerror(error: OSError) -> None:
        errors.append(f"walk_error:{error.filename}:{error.strerror}")

    for supplied in roots:
        root = supplied.expanduser().resolve()
        if not root.exists() or not root.is_dir():
            errors.append(f"unavailable_root:{root}")
            continue
        for current, dirs, files in os.walk(root, topdown=True, onerror=onerror, followlinks=False):
            dirs[:] = [name for name in dirs if name.casefold() not in BLOCKED_NAMES]
            base = Path(current)
            for name in files:
                path = base / name
                try:
                    stat = path.stat(follow_symlinks=False)
                    if not path.is_symlink():
                        index[name.casefold()].append(Candidate(str(path), name, stat.st_size, stat.st_mtime_ns))
                except (OSError, PermissionError) as exc:
                    errors.append(f"file_error:{path}:{exc.__class__.__name__}")
    return index, errors


def reconcile(wanted: Iterable[WantedFile], index: dict[str, list[Candidate]], cap: int = 50) -> list[dict]:
    results: list[dict] = []
    for item in wanted:
        candidates = index.get(item.name.casefold(), [])
        if item.size is not None:
            sized = [candidate for candidate in candidates if candidate.size == item.size]
            if sized:
                candidates = sized
        total = len(candidates)
        status = "missing" if total == 0 else "unique" if total == 1 else "ambiguous"
        results.append({
            "row": item.row,
            "requested_name": item.name,
            "requested_path": item.source_path,
            "requested_size": item.size,
            "status": status,
            "candidate_count": total,
            "overflow": total > cap,
            "candidates": [asdict(candidate) for candidate in candidates[:cap]],
            "proposed_action": "review" if status != "unique" else "link_existing",
            "mutation_authorized": False,
        })
    return results


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.casefold() == ".csv":
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            fields = ["row", "requested_name", "requested_path", "requested_size", "status",
                      "candidate_count", "overflow", "proposed_action", "candidate_paths"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for result in report["results"]:
                writer.writerow({**{key: result.get(key) for key in fields},
                                 "candidate_paths": " | ".join(c["path"] for c in result["candidates"])})
    else:
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only large-list file reconciler")
    parser.add_argument("input", type=Path, help="Excel, CSV, TSV, or text list")
    parser.add_argument("roots", nargs="+", type=Path, help="Folders to search")
    parser.add_argument("--sheet", help="Excel sheet name (default: active sheet)")
    parser.add_argument("--output", required=True, type=Path, help="Review report (.json or .csv)")
    parser.add_argument("--candidate-cap", type=int, default=50)
    args = parser.parse_args()
    if args.candidate_cap < 1:
        parser.error("--candidate-cap must be at least 1")

    wanted = load_wanted(args.input, args.sheet)
    index, errors = index_roots(args.roots)
    results = reconcile(wanted, index, args.candidate_cap)
    counts = {status: sum(r["status"] == status for r in results)
              for status in ("unique", "ambiguous", "missing")}
    report = {
        "mode": "read_only",
        "input": str(args.input.resolve()),
        "roots": [str(root.resolve()) for root in args.roots],
        "summary": {"input_rows": len(wanted), "indexed_names": len(index), **counts},
        "errors": errors,
        "results": results,
    }
    write_report(args.output, report)
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
