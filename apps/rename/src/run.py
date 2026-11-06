"""rename app entry point: PROPOSALS ONLY.

Uses the 03_RENAMING engine (DOMAIN__TYPE__words__YYYYMMDD__ST.ext, rules in
engine/rename_rules.yaml) to propose names and writes one rename-proposal.v1
record per file to data/rename/rename-proposal.v1.jsonl.

This app never renames, moves, deletes or edits anything. Every record has
review_state "proposed"; applying is a separate, human-reviewed step.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC / "engine"))
import rename_engine  # noqa: E402

APP_VERSION = "0.1.0"
ROOT = SRC.parents[2]
DEFAULT_OUT = ROOT / "data" / "rename" / "rename-proposal.v1.jsonl"
AUTO_CHECK = 0.75  # same threshold the Renamer window uses to pre-check a row


def to_records(props) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for pr in props:
        unchanged = pr.proposed == pr.path.name
        if pr.flag == "unreadable":
            status = "error"
        elif pr.flag or pr.confidence < AUTO_CHECK:
            status = "needs_review"
        elif unchanged:
            status = "skipped"
        else:
            status = "ok"
        out.append({
            "schema_version": "rename-proposal.v1", "producer": f"rename@{APP_VERSION}",
            "created_at": now, "source_path": str(pr.path), "sha256": pr.sha256 or "0" * 64,
            "status": status, "proposed_name": pr.proposed, "proposed_dir": str(pr.path.parent),
            "reason": "; ".join(pr.why), "review_state": "proposed",
            "confidence": pr.confidence, "flag": pr.flag,
            "fields": {"domain": pr.domain, "type": pr.type, "status": pr.status},
            "recovery": {"original_path": str(pr.path), "original_name": pr.path.name, "sha256": pr.sha256},
        })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="David-OS rename app (proposals only)")
    ap.add_argument("folder")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    root = Path(a.folder)
    if not root.is_dir():
        print(f"ERROR: {root} is not a folder"); return 2
    recs = to_records(rename_engine.propose(root, recursive=not a.no_recursive))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    counts = {}
    for r in recs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{len(recs)} proposals {counts} -> {a.out}  (nothing renamed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
