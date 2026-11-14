#!/usr/bin/env python3
"""Apply a batch review spec to pending equation cases."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply(spec_path: Path, queue_dir: Path, reviewer: str, model: str) -> int:
    specs = load_json(spec_path)
    pending = queue_dir / "pending"
    applied = 0
    for spec in specs:
        fp = spec["fingerprint"]
        case_path = pending / f"EQ-{fp[:12]}.json"
        if not case_path.exists():
            print(f"WARN: case not found for {fp[:12]}")
            continue
        case = load_json(case_path)
        review_entry = {
            "reviewer": reviewer,
            "model": model,
            "independent": True,
            "decision": spec["classification"],
            "confidence": spec["confidence"],
            "evidence": spec.get("evidence", []),
            "reviewed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        case["required_review"]["reviewers"].append(review_entry)
        case["required_review"]["classification"] = spec["classification"]
        case["required_review"]["canonical_id"] = spec.get("canonical_id")
        case["required_review"]["canonical_equation"] = spec.get("canonical_equation")
        case["required_review"]["math_translation"] = spec.get("math_translation")
        case["required_review"]["plain_translation"] = spec.get("plain_translation")
        case["required_review"]["theological_translation"] = spec.get("theological_translation")
        case["required_review"]["proposed_replacement"] = spec.get("proposed_replacement")
        case["status"] = "reviewed"
        save_json(case_path, case)
        applied += 1
        print(f"Reviewed {case_path.name} -> {spec['classification']}")
    print(f"Applied {applied} reviews.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply batch review spec to pending cases.")
    parser.add_argument("spec", help="JSON file with review entries")
    parser.add_argument("--queue", default=".canon-guard/equations", help="Equation queue root")
    parser.add_argument("--reviewer", default="kimi")
    parser.add_argument("--model", default="kimi-code-cli")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(apply(Path(args.spec), Path(args.queue), args.reviewer, args.model))
