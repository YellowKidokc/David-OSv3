"""Shared Stage 2B registry and filesystem helpers."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "_data" / "registry.sqlite"
TOOL_VERSION = "stage2b/1.0"
RULEBOOK_VERSION = "TAG_TAXONOMY_v0.4"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def connect_registry(path: str | Path, *, migrate: bool = False) -> sqlite3.Connection:
    db = Path(path).resolve()
    if not db.exists():
        raise FileNotFoundError(f"Registry does not exist: {db}")
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    if migrate:
        migrate_stage2b(con)
    return con


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(con, table):
        return set()
    return {row["name"] for row in con.execute(f'PRAGMA table_info("{table}")')}


def migrate_stage2b(con: sqlite3.Connection) -> None:
    """Add only the Stage 2B columns authorized by the build brief."""
    file_columns = columns(con, "files")
    if not file_columns:
        raise ValueError("Stage 1 registry is missing the files table")
    for name, definition in {
        "sidecar_written": "TEXT",
        "sidecar_source_fingerprint": "TEXT",
    }.items():
        if name not in file_columns:
            con.execute(f"ALTER TABLE files ADD COLUMN {name} {definition}")

    work_columns = columns(con, "works")
    if not work_columns:
        raise ValueError("Stage 1 registry is missing the works table")
    for name, definition in {
        "me_primary": "INTEGER CHECK(me_primary BETWEEN 1 AND 10)",
        "me_variables": "TEXT",
    }.items():
        if name not in work_columns:
            con.execute(f"ALTER TABLE works ADD COLUMN {name} {definition}")
    con.commit()


def admission_for(con: sqlite3.Connection, file_row: sqlite3.Row) -> dict[str, Any]:
    """Read Stage 2A without assuming one path-column spelling.

    Stage 2A owns these values. Missing/ambiguous/mismatched evidence fails closed.
    """
    if not table_exists(con, "admission"):
        raise ValueError("Stage 2A admission table is missing")
    cols = columns(con, "admission")
    lane_col = next((c for c in ("lane", "admission_lane") if c in cols), None)
    path_col = next((c for c in ("path", "source_path", "current_path", "file_path") if c in cols), None)
    hash_col = next((c for c in ("source_sha256", "sha256", "artifact_sha256") if c in cols), None)
    if lane_col is None or (path_col is None and hash_col is None):
        raise ValueError("Admission table lacks lane and path/hash identity columns")

    clauses: list[str] = []
    params: list[Any] = []
    if path_col:
        clauses.append(f'"{path_col}"=?')
        params.append(file_row["path"])
    if hash_col and file_row["sha256"]:
        clauses.append(f'"{hash_col}"=?')
        params.append(file_row["sha256"])
    rows = con.execute(
        f'SELECT * FROM admission WHERE {" OR ".join(clauses)}', params
    ).fetchall()
    exact = []
    for row in rows:
        data = dict(row)
        path_ok = not path_col or data.get(path_col) in (None, file_row["path"])
        hash_ok = not hash_col or data.get(hash_col) in (None, file_row["sha256"])
        if path_ok and hash_ok:
            exact.append(data)
    if len(exact) != 1:
        raise ValueError(f"Expected one source-bound admission row, found {len(exact)}")
    data = exact[0]
    lane = str(data.get(lane_col, "")).upper()
    if lane not in {"READY", "HOLD", "EXCLUDE"}:
        raise ValueError(f"Invalid admission lane: {lane!r}")

    def decoded(name: str, default: Any) -> Any:
        value = data.get(name)
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [part.strip() for part in value.split(",") if part.strip()]
        return value

    representative = data.get("is_representative")
    if representative is None and data.get("representative_sha256"):
        representative = data["representative_sha256"] == file_row["sha256"]
    return {
        "lane": lane,
        "family_id": data.get("family_id"),
        "family_relation": data.get("family_relation"),
        "is_representative": bool(representative),
        "representative_sha256": data.get("representative_sha256"),
        "reason_codes": decoded("reason_codes", []),
        "decision_authority": data.get("decision_authority", "unresolved"),
        "decision_version": data.get("decision_version", "admission-rules/v1"),
    }


def atomic_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(str(target) + ".tmp")
    data = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, target)


def log_change(
    con: sqlite3.Connection,
    run_id: str,
    action: str,
    subject: str,
    detail: dict[str, Any],
) -> None:
    cols = columns(con, "change_log")
    values: dict[str, Any] = {
        "run_id": run_id,
        "at": now(),
        "action": action,
        "subject": subject,
        "detail_json": dump(detail),
        "tool_version": TOOL_VERSION,
        "rulebook_version": RULEBOOK_VERSION,
    }
    names = [name for name in values if name in cols]
    con.execute(
        f'INSERT INTO change_log ({",".join(names)}) VALUES ({",".join("?" for _ in names)})',
        [values[name] for name in names],
    )


def source_fingerprint(row: sqlite3.Row, admission: dict[str, Any], *, me: dict[str, Any] | None = None) -> str:
    import hashlib

    owned = {
        "path": row["path"],
        "sha256": row["sha256"],
        "size": row["size"],
        "mtime_ns": row["mtime_ns"],
        "version_id": row["version_id"],
        "admission": admission,
        "me": me or {},
    }
    return hashlib.sha256(dump(owned).encode("utf-8")).hexdigest()

