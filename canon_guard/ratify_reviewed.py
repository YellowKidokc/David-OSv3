#!/usr/bin/env python3
"""Ratify all reviewed cases in the pending queue.

Use only when the human operator has authorized the ratification.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def ratify_all(queue_dir: Path, catalog: Path, ratified_by: str) -> int:
    pending = queue_dir / "pending"
    if not pending.exists():
        print("No pending queue.")
        return 0
    ratified = 0
    for case_path in sorted(pending.glob("EQ-*.json")):
        case = json.loads(case_path.read_text(encoding="utf-8"))
        if case.get("status") != "reviewed":
            continue
        cmd = [
            sys.executable, "equation_workflow.py", "ratify", str(case_path),
            "--catalog", str(catalog),
            "--ratified-by", ratified_by,
            "--human-ratified",
            "--human-override",
        ]
        print(" ".join(cmd))
        result = subprocess.run(cmd)
        if result.returncode == 0:
            ratified += 1
        else:
            print(f"FAILED: {case_path.name}", file=sys.stderr)
    print(f"Ratified {ratified} cases.")
    return 0


if __name__ == "__main__":
    import json
    parser = argparse.ArgumentParser(description="Ratify reviewed equation cases.")
    parser.add_argument("--queue", default=".canon-guard/equations")
    parser.add_argument("--catalog", default="equation-catalog.json")
    parser.add_argument("--ratified-by", default="David")
    args = parser.parse_args()
    raise SystemExit(ratify_all(Path(args.queue), Path(args.catalog), args.ratified_by))
