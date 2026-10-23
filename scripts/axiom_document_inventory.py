#!/usr/bin/env python3
"""Inventory local documents whose name or extracted text mentions axiom(s).

This is an observe-only David-OS/FIS intake. It never moves, renames, deletes,
or rewrites source files. Matching records are fingerprinted and emitted as
CSV, JSON, and readable Markdown with the FIS content code DOC.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE = REPO_ROOT / "engine"
import sys
sys.path.insert(0, str(ENGINE))

from text_extractor import extract_text  # noqa: E402

TERM = re.compile(r"\baxioms?\b", re.IGNORECASE)
DOCUMENT_EXTENSIONS = {".md", ".txt", ".html", ".htm", ".rtf", ".pdf", ".docx", ".doc"}
SKIP_DIRS = {
    "$recycle.bin", "system volume information", ".git", "node_modules",
    ".venv", "venv", "__pycache__", ".stversions", ".trash",
    "windows", "program files", "program files (x86)", "programdata",
    "appdata", "target", "dist", "build",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_documents(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name.lower() not in SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() in DOCUMENT_EXTENSIONS:
                yield path


def scan(roots: list[Path], max_bytes: int) -> tuple[list[dict], dict]:
    matches, unreadable, inspected = [], 0, 0
    for root in roots:
        for path in iter_documents(root):
            inspected += 1
            name_match = bool(TERM.search(path.name))
            text = extract_text(str(path), max_bytes)
            text_match = bool(TERM.search(text or ""))
            if not text and path.suffix.lower() in {".pdf", ".docx", ".doc"}:
                unreadable += 1
            if not (name_match or text_match):
                continue
            try:
                stat = path.stat()
                matches.append({
                    "path": str(path),
                    "name": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": stat.st_size,
                    "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "sha256": sha256(path),
                    "matched_in": "name_and_content" if name_match and text_match else "name" if name_match else "content",
                    "fis_content_type": "document",
                    "fis_content_code": "DOC",
                    "status": "INVENTORIED_NOT_MOVED",
                })
            except OSError:
                continue
    return matches, {"documents_inspected": inspected, "unreadable_binary_documents": unreadable}


def write_outputs(records: list[dict], summary: dict, output: Path, roots: list[Path]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = list(records[0]) if records else [
        "path", "name", "extension", "size_bytes", "modified_utc", "sha256",
        "matched_in", "fis_content_type", "fis_content_code", "status",
    ]
    with (output / "AXIOM_DOCUMENT_INVENTORY.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(records)
    payload = {"schema": "david-os.axiom-document-inventory.v1", "created_utc": stamp,
               "roots": [str(x) for x in roots], "authority": "OBSERVE_ONLY_NOT_CANON",
               "summary": {**summary, "matches": len(records)}, "records": records}
    (output / "AXIOM_DOCUMENT_INVENTORY.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    duplicate_groups = len({x["sha256"] for x in records})
    lines = ["# AXIOM Document Inventory", "", f"Generated: `{stamp}`", "",
             "> [!warning] Observe-only inventory",
             "> These files were indexed as `DOC`; originals were not moved, renamed, deleted, or admitted to canon.", "",
             "## Summary", "", f"- Roots scanned: {', '.join(f'`{x}`' for x in roots)}",
             f"- Documents inspected: {summary['documents_inspected']}", f"- AXIOM matches: {len(records)}",
             f"- Unique content hashes: {duplicate_groups}",
             f"- Unreadable PDF/DOC/DOCX candidates: {summary['unreadable_binary_documents']}", "", "## Files", ""]
    for item in records:
        lines.extend([f"### {item['name']}", "", f"- Path: `{item['path']}`",
                      f"- Match: {item['matched_in']}", f"- FIS type: `DOC`",
                      f"- SHA-256: `{item['sha256']}`", ""])
    (output / "AXIOM_DOCUMENT_INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe-only inventory of AXIOM documents")
    parser.add_argument("--roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "docs" / "AXIOM_DOCUMENT_INVENTORY")
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
    args = parser.parse_args()
    roots = [root.resolve() for root in args.roots if root.exists()]
    records, summary = scan(roots, args.max_bytes)
    write_outputs(records, summary, args.output.resolve(), roots)
    print(json.dumps({**summary, "matches": len(records), "output": str(args.output.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
