"""Apply an explicitly approved vault-transfer plan across volumes safely.

The existing Station 104 applier correctly permits only same-volume renames.
This separate worker handles an explicitly approved cross-volume batch:

1. Preflight every source/target and reject collisions.
2. Copy every source to a uniquely named temporary destination.
3. SHA-256 verify every staged copy while every original still exists.
4. Atomically promote all staged copies to their final destination names.
5. Re-verify each final and remove its source.
6. Write a receipt and a reverse/undo plan beside the input plan.

Nothing is inferred as approved. Use --approve-all only after a human has
explicitly approved the entire supplied plan. No destination is overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid


SCHEMA = "vault-transfer-plan/1"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_plan(path: Path, approve_all: bool) -> tuple[dict, list[dict]]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("schema") != SCHEMA:
        raise ValueError(f"unsupported plan schema: {plan.get('schema')}")
    items = list(plan.get("items", []))
    selected = items if approve_all else [item for item in items if item.get("status") == "APPROVED"]
    if not selected:
        raise ValueError("no approved items; use reviewed statuses or explicit --approve-all")
    return plan, selected


def preflight(items: list[dict], target_root: Path) -> list[dict]:
    targets, rows = set(), []
    for item in items:
        source = Path(item["source_path"])
        target = Path(item["proposed_destination"])
        target_key = str(target).casefold()
        if target_key in targets:
            raise ValueError(f"duplicate destination: {target}")
        targets.add(target_key)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(source)
        if not inside(target, target_root):
            raise ValueError(f"destination escapes intended vault: {target}")
        if target.exists():
            raise FileExistsError(target)
        rows.append({"source": str(source), "target": str(target), "size": source.stat().st_size})
    return rows


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def apply(plan_path: Path, plan: dict, items: list[dict], target_root: Path) -> int:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    receipt_path = plan_path.parent / f"RECEIPT_CROSS_VOLUME_{run_id}.json"
    undo_path = plan_path.parent / f"UNDO_CROSS_VOLUME_{run_id}.json"
    staged: list[dict] = []
    receipt = {
        "schema": "david-os.cross-volume-routing-receipt.v1",
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "plan": str(plan_path),
        "approval": "human explicitly approved entire plan",
        "state": "STAGING",
        "items": [],
    }
    write_json(receipt_path, receipt)
    try:
        # Phase 1: no source is removed until the entire batch is staged and verified.
        for number, item in enumerate(items, 1):
            source = Path(item["source_path"])
            target = Path(item["proposed_destination"])
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + f".david-os-staging-{run_id}")
            if temporary.exists():
                raise FileExistsError(temporary)
            source_hash = digest(source)
            shutil.copy2(source, temporary)
            staged_hash = digest(temporary)
            if staged_hash != source_hash or temporary.stat().st_size != source.stat().st_size:
                raise OSError(f"staged verification failed: {source}")
            row = {"source": str(source), "target": str(target), "temporary": str(temporary),
                   "sha256": source_hash, "size": source.stat().st_size, "state": "STAGED_VERIFIED"}
            staged.append(row)
            receipt["items"].append(row)
            if number % 25 == 0:
                write_json(receipt_path, receipt)
                print(f"  staged and verified {number}/{len(items)}", flush=True)

        # Phase 2: make all verified copies visible. Originals still all exist.
        for row in staged:
            os.replace(row["temporary"], row["target"])
            row["state"] = "FINALIZED_SOURCE_RETAINED"
        receipt["state"] = "FINALIZED_SOURCE_RETAINED"
        write_json(receipt_path, receipt)

        # Phase 3: one last verification, then remove each original.
        removed = 0
        for row in staged:
            source, target = Path(row["source"]), Path(row["target"])
            if digest(target) != row["sha256"]:
                raise OSError(f"final verification failed; source retained: {target}")
            source.unlink()
            row["state"] = "MOVED_VERIFIED"
            removed += 1
            if removed % 25 == 0:
                write_json(receipt_path, receipt)
                print(f"  source removal verified {removed}/{len(items)}", flush=True)

        receipt["state"] = "COMPLETE"
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
        receipt["moved"] = len(staged)
        write_json(receipt_path, receipt)
        undo = {
            "schema": SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_root": str(target_root),
            "proposed_by": f"undo of {run_id}",
            "items": [{"source_path": row["target"], "proposed_destination": row["source"],
                       "status": "APPROVED", "expected_sha256": row["sha256"],
                       "reason": f"undo verified cross-volume move {run_id}"} for row in staged],
        }
        write_json(undo_path, undo)
        print(f"COMPLETE: moved and verified {len(staged)} files")
        print(f"Receipt: {receipt_path}")
        print(f"Undo plan: {undo_path}")
        return 0
    except Exception as exc:
        # Remove only hidden staging files. Never remove a finalized verified copy
        # or an original during error cleanup; the receipt exposes both locations.
        for row in staged:
            temporary = Path(row["temporary"])
            if temporary.exists():
                temporary.unlink()
        receipt["state"] = "NEEDS_REVIEW"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(receipt_path, receipt)
        print(f"STOPPED SAFELY: {exc}", file=sys.stderr)
        print(f"Receipt: {receipt_path}", file=sys.stderr)
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--approve-all", action="store_true", help="human approved every item in this exact plan")
    parser.add_argument("--series-override", action="store_true", help="human reviewed and accepts the plan's series splits")
    parser.add_argument("--source-prefix", help="apply only selected items whose source_path is under this prefix")
    parser.add_argument("--exclude-source-prefix", help="exclude selected items whose source_path is under this prefix")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan, items = load_plan(args.plan, args.approve_all)
    if args.source_prefix:
        prefix = str(Path(args.source_prefix)).rstrip("\\/").casefold() + os.sep
        items = [item for item in items if str(Path(item["source_path"])).casefold().startswith(prefix)]
        if not items:
            raise SystemExit(f"no selected items matched --source-prefix {args.source_prefix}")
    if args.exclude_source_prefix:
        prefix = str(Path(args.exclude_source_prefix)).rstrip("\\/").casefold() + os.sep
        items = [item for item in items if not str(Path(item["source_path"])).casefold().startswith(prefix)]
        if not items:
            raise SystemExit(f"no selected items remained after --exclude-source-prefix {args.exclude_source_prefix}")
    if args.approve_all and not args.series_override:
        raise SystemExit("--approve-all requires --series-override after series-context review")
    rows = preflight(items, args.target_root)
    total = sum(row["size"] for row in rows)
    print(f"PREFLIGHT PASS: {len(rows)} files, {total:,} bytes")
    print(f"Target root: {args.target_root}")
    print("Approval: all plan items" if args.approve_all else "Approval: APPROVED statuses only")
    if not args.apply:
        print("DRY RUN: no files changed. Add --apply to execute copy/hash-verify/remove.")
        return 0
    return apply(args.plan, plan, items, args.target_root)


if __name__ == "__main__":
    raise SystemExit(main())
