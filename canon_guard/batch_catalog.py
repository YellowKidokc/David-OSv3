#!/usr/bin/env python3
"""Batch-create equation review cases from a pre-computed extraction list.

This lets the equation workflow scale past the one-equation-at-a-time stop.
After cases are created, use equation_workflow.py review + ratify on each case.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from equation_workflow import load_json, make_case


class _Eq:
    def __init__(self, raw: str, normalized: str, line: int, fingerprint: str):
        self.raw = raw
        self.normalized = normalized
        self.line = line
        self.fingerprint = fingerprint


def batch_scan(root: Path, catalog_path: Path, queue_dir: Path, extraction_path: Path) -> int:
    catalog = load_json(catalog_path, {"schema": 1, "equations": []})
    known = {item["fingerprint"] for item in catalog.get("equations", [])}
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    root = root.resolve()
    created = 0
    skipped = 0
    for item in extraction:
        fp = item["fingerprint"]
        if fp in known:
            skipped += 1
            continue
        eq = _Eq(item["raw"], item["normalized"], item["line"], fp)
        path = root / item["path"]
        make_case(path, root, eq, queue_dir)
        created += 1
    print(f"Created {created} pending cases; skipped {skipped} already cataloged.")
    print(f"Queue: {queue_dir / 'pending'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch-create equation review cases.")
    parser.add_argument("root", help="Root of the scanned tree (e.g., C:/theophysics/_INBOX/Master_Equation)")
    parser.add_argument("extraction", help="JSON file produced by extraction script")
    parser.add_argument("--catalog", default="equation-catalog.json")
    parser.add_argument("--queue", default=".canon-guard/equations")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(batch_scan(Path(args.root), Path(args.catalog), Path(args.queue), Path(args.extraction)))
