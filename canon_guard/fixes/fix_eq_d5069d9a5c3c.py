#!/usr/bin/env python3
"""Propose EQ-d5069d9a5c3c. Generated from a human-ratified equation case.

This script NEVER edits the source. It writes a corrected copy and unified diff.
"""
import argparse, difflib, hashlib
from pathlib import Path

EXPECTED_SOURCE_HASH = '082fae2f3083b27cfb2dff7b38e8a48167c5d25d33b0cc911e5168f5ab88c102'
OLD = '∂ρ/∂t = Grace·Redemption·Covenant + ...'
NEW = '∂ρ/∂t = η(ρ,t) + L(ρ)'

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--output-dir", default="fix-output/EQ-d5069d9a5c3c")
args = parser.parse_args()
source = Path(args.source).resolve()
data = source.read_bytes()
actual = hashlib.sha256(data).hexdigest()
if actual != EXPECTED_SOURCE_HASH:
    raise SystemExit("Refusing proposal: source changed since the review case was created.")
text = data.decode("utf-8")
if text.count(OLD) != 1:
    raise SystemExit("Refusing proposal: expected equation is not a unique exact match.")
updated = text.replace(OLD, NEW, 1)
out_dir = Path(args.output_dir).resolve()
out_dir.mkdir(parents=True, exist_ok=True)
corrected = out_dir / source.name
patch = out_dir / (source.name + ".patch")
corrected.write_text(updated, encoding="utf-8")
patch.write_text("".join(difflib.unified_diff(
    text.splitlines(keepends=True), updated.splitlines(keepends=True),
    fromfile=str(source), tofile=str(corrected))), encoding="utf-8")
print(corrected)
print(patch)
