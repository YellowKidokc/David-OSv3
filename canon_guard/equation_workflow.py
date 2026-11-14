#!/usr/bin/env python3
"""Unknown-equation queue, ratification memory, and non-mutating fix generator."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

from canon_guard import extract_equations, normalize_equation, sha256_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCHEMA = 1


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def catalog_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["fingerprint"]: item for item in catalog.get("equations", [])}


def make_case(path: Path, root: Path, equation: Any, output_dir: Path) -> Path:
    case_id = f"EQ-{equation.fingerprint[:12]}"
    destination = output_dir / "pending" / f"{case_id}.json"
    if destination.exists():
        return destination
    case = {
        "schema": SCHEMA,
        "case_id": case_id,
        "status": "pending",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {
            "path": path.relative_to(root).as_posix(),
            "line": equation.line,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
        "equation": {
            "raw": equation.raw,
            "normalized": equation.normalized,
            "fingerprint": equation.fingerprint,
        },
        "required_review": {
            "classification": ["equivalent", "compatible", "drift", "new_canonical_candidate", "not_an_equation"],
            "math_translation": None,
            "plain_translation": None,
            "theological_translation": None,
            "canonical_id": None,
            "canonical_equation": None,
            "confidence": None,
            "evidence": [],
            "reviewers": [],
            "proposed_replacement": None,
        },
        "policy": {
            "minimum_independent_approvals": 2,
            "human_ratification_required_for_canon_change": True,
            "source_mutation_allowed": False,
        },
    }
    write_json(destination, case)
    return destination


def scan(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    catalog_path = Path(args.catalog).resolve()
    queue = Path(args.queue).resolve()
    catalog = load_json(catalog_path, {"schema": SCHEMA, "equations": []})
    known = catalog_index(catalog)
    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                   {".md", ".txt", ".tex", ".lean"})
    count = 0
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for equation in extract_equations(text, strict=True):
            if equation.fingerprint in known:
                continue
            case_path = make_case(path, root, equation, queue)
            print(f"STOP unknown equation: {equation.raw}")
            print(f"Review case: {case_path}")
            return 2
        count += 1
    print(f"All equations cataloged across {count} files.")
    return 0


def review(args: argparse.Namespace) -> int:
    case_path = Path(args.case).resolve()
    case = load_json(case_path, None)
    if not case:
        raise ValueError("case does not exist")
    reviewer = {
        "reviewer": args.reviewer,
        "model": args.model,
        "independent": not args.not_independent,
        "decision": args.decision,
        "confidence": args.confidence,
        "evidence": args.evidence or [],
        "reviewed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    case["required_review"]["reviewers"].append(reviewer)
    case["required_review"]["classification"] = args.decision
    for key in ("math_translation", "plain_translation", "theological_translation",
                "canonical_id", "canonical_equation", "proposed_replacement"):
        value = getattr(args, key)
        if value is not None:
            case["required_review"][key] = value
    case["status"] = "reviewed"
    write_json(case_path, case)
    print(f"Recorded independent review in {case_path}")
    return 0


def ratify(args: argparse.Namespace) -> int:
    case_path = Path(args.case).resolve()
    catalog_path = Path(args.catalog).resolve()
    fixes_dir = Path(args.fixes).resolve()
    case = load_json(case_path, None)
    if not case:
        raise ValueError("case does not exist")
    review = case["required_review"]
    independent = [r for r in review["reviewers"] if r.get("independent")]
    minimum = int(case["policy"]["minimum_independent_approvals"])
    if len(independent) < minimum and not args.human_override:
        raise ValueError(f"needs {minimum} independent reviews; has {len(independent)}")
    if not args.human_ratified:
        raise ValueError("ratification requires --human-ratified")
    classification = review["classification"]
    catalog = load_json(catalog_path, {"schema": SCHEMA, "equations": []})
    entry = {
        "id": case["case_id"],
        "fingerprint": case["equation"]["fingerprint"],
        "normalized": case["equation"]["normalized"],
        "canonical_id": review.get("canonical_id"),
        "classification": classification,
        "math_translation": review.get("math_translation"),
        "plain_translation": review.get("plain_translation"),
        "theological_translation": review.get("theological_translation"),
        "canonical_equation": review.get("canonical_equation"),
        "ratified_by": args.ratified_by,
        "ratified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_case": case_path.as_posix(),
    }
    index = catalog_index(catalog)
    if entry["fingerprint"] in index:
        raise ValueError("equation fingerprint is already cataloged")
    catalog["equations"].append(entry)
    catalog["equations"].sort(key=lambda item: item["id"])
    write_json(catalog_path, catalog)
    case["status"] = "ratified"
    write_json(case_path, case)
    print(f"Cataloged {entry['id']} in {catalog_path}")
    if classification == "drift":
        replacement = review.get("proposed_replacement")
        if not replacement:
            raise ValueError("drift ratification needs proposed_replacement")
        generated = generate_fix(case, replacement, fixes_dir)
        print(f"Generated non-mutating fix: {generated}")
    return 0


def generate_fix(case: dict[str, Any], replacement: str, fixes_dir: Path) -> Path:
    case_id = case["case_id"]
    source = case["source"]
    raw = case["equation"]["raw"]
    filename = f"fix_{case_id.lower().replace('-', '_')}.py"
    path = fixes_dir / filename
    template = f'''#!/usr/bin/env python3
"""Propose {case_id}. Generated from a human-ratified equation case.

This script NEVER edits the source. It writes a corrected copy and unified diff.
"""
import argparse, difflib, hashlib
from pathlib import Path

EXPECTED_SOURCE_HASH = {source["source_sha256"]!r}
OLD = {raw!r}
NEW = {replacement!r}

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--output-dir", default="fix-output/{case_id}")
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
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template, encoding="utf-8")
    path.chmod(0o755)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Equation catalog and ratification workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("root")
    p_scan.add_argument("--catalog", default="equation-catalog.json")
    p_scan.add_argument("--queue", default=".canon-guard/equations")
    p_scan.set_defaults(func=scan)
    p_review = sub.add_parser("review")
    p_review.add_argument("case")
    p_review.add_argument("--reviewer", required=True)
    p_review.add_argument("--model", required=True)
    p_review.add_argument("--decision", required=True,
                          choices=("equivalent", "compatible", "drift",
                                   "new_canonical_candidate", "not_an_equation"))
    p_review.add_argument("--confidence", type=float, required=True)
    p_review.add_argument("--evidence", action="append")
    p_review.add_argument("--not-independent", action="store_true")
    for name in ("math_translation", "plain_translation", "theological_translation",
                 "canonical_id", "canonical_equation", "proposed_replacement"):
        p_review.add_argument("--" + name.replace("_", "-"), dest=name)
    p_review.set_defaults(func=review)
    p_ratify = sub.add_parser("ratify")
    p_ratify.add_argument("case")
    p_ratify.add_argument("--catalog", default="equation-catalog.json")
    p_ratify.add_argument("--fixes", default="fixes")
    p_ratify.add_argument("--ratified-by", required=True)
    p_ratify.add_argument("--human-ratified", action="store_true")
    p_ratify.add_argument("--human-override", action="store_true")
    p_ratify.set_defaults(func=ratify)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"equation-workflow: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
