#!/usr/bin/env python3
"""Headless observe-only Master Equation intake command."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.master_equation_intake import analyze  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a Master Equation corpus without mutating it.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = analyze(args.source, args.output)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

