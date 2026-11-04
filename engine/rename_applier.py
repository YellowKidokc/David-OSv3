"""Approval-bound Stage 2B rename applier with preview and conflict-safe undo.

Safe default:
  python -m engine.rename_applier preview PATH

Mutation requires both the ``apply`` subcommand and ``--confirm``.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from engine.fingerprint import sha256_file
from engine.gate import BLOCK, DROP, Gate
from engine.stage2b_common import (
    DEFAULT_DB,
    REPO,
    atomic_json,
    columns,
    connect_registry,
    log_change,
    now,
    table_exists,
)

AUTO_THRESHOLD = 0.72


def _sidecars(root: Path) -> list[Path]:
    return sorted(root.rglob("*.fis.json"), key=lambda p: str(p).lower())


def _source_for(sidecar: Path) -> Path:
    return Path(str(sidecar)[: -len(".fis.json")])


def _eligible(payload: dict[str, Any], *, auto_only: bool) -> tuple[bool, str]:
    admission = payload.get("admission") or {}
    lane = str(admission.get("lane", "HOLD")).upper()
    if lane != "READY":
        return False, f"admission lane {lane or 'missing'}"
    approved = payload.get("rename_approved") is True
    score = float(payload.get("rename_score") or 0.0)
    auto = payload.get("rename_decision") == "auto_approve" and score >= AUTO_THRESHOLD
    if auto_only:
        return (auto, "auto threshold not met" if not auto else "auto-approved candidate")
    if not (approved or auto):
        return False, "rename is neither approved nor an explicitly confirmed auto candidate"
    return True, "human-approved" if approved else "auto candidate requiring batch confirmation"


def _collision_safe_target(source: Path, proposed_name: str) -> Path:
    target = source.with_name(proposed_name)
    if target == source or (not target.exists() and not Path(str(target) + ".fis.json").exists()):
        return target
    stem, suffix = target.stem, target.suffix
    counter = 2
    while True:
        candidate = target.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists() and not Path(str(candidate) + ".fis.json").exists():
            return candidate
        counter += 1


def _gate(source: Path, target: Path, score: float, batch_size: int) -> dict[str, Any]:
    gate = Gate.load(REPO / "config" / "rules", {"approval_floor": "approval_required"})
    return gate.evaluate(
        "rename", [str(source), str(target)],
        {"confidence": score, "review_threshold": AUTO_THRESHOLD,
         "collision": target.exists(), "batch_size": batch_size},
    ).to_json()


def plan(root: str | Path, *, auto_only: bool = False, batch: str | Path | None = None) -> list[dict[str, Any]]:
    root_path = Path(root).resolve(strict=True)
    approved_batch: set[str] | None = None
    if batch:
        raw = json.loads(Path(batch).read_text(encoding="utf-8"))
        entries = raw.get("renames", raw) if isinstance(raw, dict) else raw
        approved_batch = {
            str(item.get("source") if isinstance(item, dict) else item)
            for item in entries
        }
    candidates: list[dict[str, Any]] = []
    all_sidecars = _sidecars(root_path)
    for sidecar in all_sidecars:
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            source = _source_for(sidecar)
            if approved_batch is not None and str(source) not in approved_batch:
                continue
            ok, reason = _eligible(payload, auto_only=auto_only)
            proposed = payload.get("proposed_name")
            if not source.exists():
                ok, reason = False, "source is missing"
            elif isinstance(payload.get("source"), dict) and payload["source"].get("sha256"):
                if sha256_file(str(source)) != payload["source"]["sha256"]:
                    ok, reason = False, "source hash changed since sidecar generation"
            if not proposed:
                ok, reason = False, "no proposed_name"
                target = None
            else:
                target = _collision_safe_target(source, str(proposed))
                if target == source:
                    ok, reason = False, "already has proposed name"
            gate = _gate(source, target or source, float(payload.get("rename_score") or 0), len(all_sidecars))
            if gate["verdict"] in {BLOCK, DROP}:
                ok, reason = False, f"gate {gate['verdict']}"
            candidates.append({
                "sidecar": str(sidecar), "source": str(source),
                "target": str(target) if target else None, "eligible": ok,
                "reason": reason, "gate": gate,
            })
        except Exception as exc:
            candidates.append({"sidecar": str(sidecar), "eligible": False, "reason": str(exc)})
    return candidates


def _replace_references(value: Any, old: str, new: str) -> tuple[Any, bool]:
    if isinstance(value, str):
        return (new, True) if value == old else (value, False)
    if isinstance(value, list):
        changed = False
        result = []
        for item in value:
            converted, item_changed = _replace_references(item, old, new)
            result.append(converted)
            changed |= item_changed
        return result, changed
    if isinstance(value, dict):
        changed = False
        result = {}
        for key, item in value.items():
            converted, item_changed = _replace_references(item, old, new)
            result[key] = converted
            changed |= item_changed
        return result, changed
    return value, False


def _update_canon_sidecars(folder: Path, old: str, new: str) -> list[Path]:
    changed_paths = []
    for path in folder.rglob("*.canon.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        converted, changed = _replace_references(payload, old, new)
        if changed:
            atomic_json(path, converted)
            changed_paths.append(path)
    return changed_paths


def _update_admission_path(con: sqlite3.Connection, old: str, new: str) -> None:
    if not table_exists(con, "admission"):
        raise ValueError("Stage 2A admission table is missing")
    cols = columns(con, "admission")
    path_col = next((c for c in ("path", "source_path", "current_path", "file_path") if c in cols), None)
    if path_col:
        con.execute(f'UPDATE admission SET "{path_col}"=? WHERE "{path_col}"=?', (new, old))


def _update_registry_path(con: sqlite3.Connection, old: str, new: str) -> None:
    row = con.execute("SELECT version_id FROM files WHERE path=?", (old,)).fetchone()
    con.execute("UPDATE files SET path=? WHERE path=?", (new, old))
    if row and row["version_id"]:
        version = con.execute(
            "SELECT files_json FROM versions WHERE version_id=?", (row["version_id"],)
        ).fetchone()
        if version:
            paths = json.loads(version["files_json"])
            paths = [new if value == old else value for value in paths]
            con.execute(
                "UPDATE versions SET files_json=? WHERE version_id=?",
                (json.dumps(sorted(set(paths)), ensure_ascii=False, sort_keys=True), row["version_id"]),
            )
    _update_admission_path(con, old, new)


def _apply_one(
    con: sqlite3.Connection, item: dict[str, Any], changeset_id: str, reference_root: Path
) -> dict[str, Any]:
    old = Path(item["source"])
    new = Path(item["target"])
    old_sidecar = Path(item["sidecar"])
    new_sidecar = Path(str(new) + ".fis.json")
    payload = json.loads(old_sidecar.read_text(encoding="utf-8"))
    digest = sha256_file(str(old))
    os.rename(old, new)
    try:
        payload["renamed_from"] = old.name
        payload["renamed_at"] = now()
        if isinstance(payload.get("source"), dict):
            payload["source"]["path"] = str(new)
            payload["source"]["name"] = new.name
        atomic_json(new_sidecar, payload)
        old_sidecar.unlink()
        _update_canon_sidecars(reference_root, str(old), str(new))
        _update_registry_path(con, str(old), str(new))
        detail = {
            "old_path": str(old), "new_path": str(new), "timestamp": now(),
            "reason": item["reason"], "changeset_id": changeset_id,
            "sha256": digest,
            "reference_root": str(reference_root),
        }
        log_change(con, changeset_id, "rename_applied", str(new), detail)
        con.commit()
        return detail
    except Exception:
        con.rollback()
        if new_sidecar.exists() and not old_sidecar.exists():
            os.rename(new_sidecar, old_sidecar)
        if new.exists() and not old.exists():
            os.rename(new, old)
        raise


def apply(
    root: str | Path, *, db_path: str | Path = DEFAULT_DB, confirm: bool = False,
    auto_only: bool = False, interactive: bool = False, batch: str | Path | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise ValueError("Refusing mutation: apply requires --confirm")
    candidates = plan(root, auto_only=auto_only, batch=batch)
    reference_root = Path(root).resolve(strict=True)
    changeset_id = str(uuid.uuid4())
    result: dict[str, Any] = {"changeset_id": changeset_id, "renamed": [], "skipped": [], "errors": []}
    with connect_registry(db_path, migrate=True) as con:
        for item in candidates:
            if not item.get("eligible"):
                result["skipped"].append(item)
                continue
            if interactive:
                answer = input(f"Rename {item['source']} -> {item['target']}? [y/N/edit] ").strip().lower()
                if answer == "edit":
                    name = input("New filename: ").strip()
                    if not name or Path(name).name != name:
                        result["skipped"].append({**item, "reason": "invalid edited filename"})
                        continue
                    item["target"] = str(_collision_safe_target(Path(item["source"]), name))
                elif answer not in {"y", "yes"}:
                    result["skipped"].append({**item, "reason": "interactive rejection"})
                    continue
            try:
                result["renamed"].append(_apply_one(con, item, changeset_id, reference_root))
            except Exception as exc:
                result["errors"].append({**item, "error": str(exc)})
    return result


def undo(changeset_id: str, *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    result: dict[str, Any] = {"changeset_id": changeset_id, "restored": [], "errors": []}
    with connect_registry(db_path, migrate=True) as con:
        rows = con.execute(
            "SELECT * FROM change_log WHERE run_id=? AND action='rename_applied' ORDER BY id DESC",
            (changeset_id,),
        ).fetchall()
        if not rows:
            raise ValueError(f"No applied renames found for changeset {changeset_id}")
        for row in rows:
            detail = json.loads(row["detail_json"])
            old, new = Path(detail["old_path"]), Path(detail["new_path"])
            try:
                if old.exists():
                    raise FileExistsError(f"Undo target already exists: {old}")
                if not new.exists():
                    raise FileNotFoundError(new)
                if sha256_file(str(new)) != detail["sha256"]:
                    raise ValueError(f"Undo refused: content changed since rename: {new}")
                new_sidecar, old_sidecar = Path(str(new) + ".fis.json"), Path(str(old) + ".fis.json")
                os.rename(new, old)
                if new_sidecar.exists():
                    payload = json.loads(new_sidecar.read_text(encoding="utf-8"))
                    payload["undo_of"] = changeset_id
                    payload["renamed_at"] = now()
                    if isinstance(payload.get("source"), dict):
                        payload["source"]["path"] = str(old)
                        payload["source"]["name"] = old.name
                    atomic_json(old_sidecar, payload)
                    new_sidecar.unlink()
                _update_canon_sidecars(Path(detail.get("reference_root", old.parent)), str(new), str(old))
                _update_registry_path(con, str(new), str(old))
                log_change(con, changeset_id, "rename_undone", str(old), detail)
                con.commit()
                result["restored"].append({"from": str(new), "to": str(old)})
            except Exception as exc:
                con.rollback()
                result["errors"].append({"detail": detail, "error": str(exc)})
    return result


def _write_report(result: Any, db_path: Path, name: str) -> None:
    target = db_path.resolve().parent / name
    target.write_text("# Stage 2B Rename Report\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preview = sub.add_parser("preview")
    preview.add_argument("path", type=Path)
    preview.add_argument("--db", type=Path, default=DEFAULT_DB)
    preview.add_argument("--report", action="store_true")
    preview.add_argument("--auto-only", action="store_true")
    preview.add_argument("--batch", type=Path)
    execute = sub.add_parser("apply")
    execute.add_argument("path", type=Path)
    execute.add_argument("--db", type=Path, default=DEFAULT_DB)
    execute.add_argument("--report", action="store_true")
    execute.add_argument("--confirm", action="store_true")
    execute.add_argument("--auto-only", action="store_true")
    execute.add_argument("--interactive", action="store_true")
    execute.add_argument("--batch", type=Path)
    reverse = sub.add_parser("undo")
    reverse.add_argument("changeset_id")
    reverse.add_argument("--db", type=Path, default=DEFAULT_DB)
    reverse.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "preview":
        result = plan(args.path, auto_only=args.auto_only, batch=args.batch)
    elif args.command == "apply":
        result = apply(args.path, db_path=args.db, confirm=args.confirm, auto_only=args.auto_only,
                       interactive=args.interactive, batch=args.batch)
    else:
        result = undo(args.changeset_id, db_path=args.db)
    if args.report:
        _write_report(result, args.db, "rename_report.md")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if isinstance(result, dict) and result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())

