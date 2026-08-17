"""
metadata_db.py — SQLite current-state store (the inventory database).

SQLite holds *current* state and is path-keyed + additive (re-scanning a file
upserts its row). History lives in the JSONL ledger, not here. The schema is
clean and self-contained; this is filebrain.sqlite, NOT the 819k-row reference
catalog (that stays read-only).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path           TEXT PRIMARY KEY,
    name           TEXT,
    ext            TEXT,
    size_bytes     INTEGER,
    sha256         TEXT,
    modified_at    TEXT,
    created_at     TEXT,
    source_root    TEXT,
    first_seen_at  TEXT,
    last_seen_at   TEXT,
    fs_status      TEXT DEFAULT 'active',   -- active | missing
    -- classification (5 tags + chi profile)
    domain         TEXT,
    domain_label   TEXT,
    content_type   TEXT,
    status         TEXT,
    date           TEXT,
    topic_slug     TEXT,
    chi_vector     TEXT,                     -- json
    chi_primary    TEXT,
    chi_secondary  TEXT,
    chi_confidence REAL,
    domain_scores  TEXT,                     -- json
    evidence       REAL,
    fruit          REAL,
    anti_fruit     REAL,
    tags           TEXT,                     -- json
    role           TEXT DEFAULT 'unknown',
    gate_category  TEXT,
    gate_tier      TEXT,
    gate_route     TEXT,
    gate_access    TEXT,
    classified_at  TEXT,
    -- proposal / review
    proposed_name  TEXT,
    decision       TEXT,                     -- auto_approve | queue | skip
    reason         TEXT,
    confidence     REAL,
    approved       INTEGER,                  -- NULL=pending, 1=yes, 0=no
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_sha   ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_appr  ON files(approved);
CREATE INDEX IF NOT EXISTS idx_files_dom   ON files(domain);

CREATE TABLE IF NOT EXISTS scan_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    roots       TEXT,
    file_types  TEXT,
    file_count  INTEGER
);
"""

_JSON_FIELDS = {"chi_vector", "domain_scores", "tags"}


# Columns that may be missing from an older filebrain.sqlite (schema grew over
# time). The DB is additive: we ALTER in anything absent instead of failing.
_EXPECTED_COLS = {
    "gate_category": "TEXT", "gate_tier": "TEXT", "gate_route": "TEXT",
    "gate_access": "TEXT",
}


def _migrate(con: sqlite3.Connection) -> None:
    existing = {r[1] for r in con.execute("PRAGMA table_info(files)").fetchall()}
    for col, typ in _EXPECTED_COLS.items():
        if col not in existing:
            try:
                con.execute(f"ALTER TABLE files ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
    con.commit()


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    con = sqlite3.connect(db_path or str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    _migrate(con)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_by_hash(con: sqlite3.Connection, sha256: str, exclude_path: str = "") -> List[sqlite3.Row]:
    """Other rows with the same content hash — used for copy/move detection."""
    rows = con.execute("SELECT * FROM files WHERE sha256=?", (sha256,)).fetchall()
    return [r for r in rows if r["path"] != exclude_path]


def get_one(con: sqlite3.Connection, path: str) -> Optional[sqlite3.Row]:
    return con.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()


def upsert_file(con: sqlite3.Connection, rec: dict) -> None:
    """Path-keyed additive upsert of a FileRecord-shaped dict."""
    now = _now()
    cols = [
        "path", "name", "ext", "size_bytes", "sha256", "modified_at", "created_at",
        "source_root", "domain", "domain_label", "content_type", "status", "date",
        "topic_slug", "chi_vector", "chi_primary", "chi_secondary", "chi_confidence",
        "domain_scores", "evidence", "fruit", "anti_fruit", "tags", "role",
        "gate_category", "gate_tier", "gate_route", "gate_access",
        "classified_at", "proposed_name", "decision", "reason", "confidence",
        "approved", "notes",
    ]
    # FileRecord uses "extension"; DB column is "ext"
    src = dict(rec)
    src.setdefault("ext", src.get("extension"))
    vals = {}
    for c in cols:
        v = src.get(c)
        if c in _JSON_FIELDS and isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        vals[c] = v
    vals["classified_at"] = vals.get("classified_at") or now

    existing = get_one(con, src["path"])
    if existing is None:
        vals["first_seen_at"] = now
        vals["last_seen_at"] = now
        placeholders = ", ".join(["?"] * (len(cols) + 2))
        con.execute(
            f"INSERT INTO files ({', '.join(cols)}, first_seen_at, last_seen_at) "
            f"VALUES ({placeholders})",
            [vals[c] for c in cols] + [now, now],
        )
    else:
        set_clause = ", ".join(f"{c}=?" for c in cols) + ", last_seen_at=?"
        con.execute(
            f"UPDATE files SET {set_clause} WHERE path=?",
            [vals[c] for c in cols] + [now, src["path"]],
        )


def start_run(con: sqlite3.Connection, roots: list, file_types: list) -> int:
    cur = con.execute(
        "INSERT INTO scan_runs (started_at, roots, file_types, file_count) VALUES (?,?,?,0)",
        (_now(), json.dumps(roots), json.dumps(file_types)),
    )
    return cur.lastrowid


def finish_run(con: sqlite3.Connection, run_id: int, file_count: int) -> None:
    con.execute("UPDATE scan_runs SET file_count=? WHERE run_id=?", (file_count, run_id))


def pending_queue(con: sqlite3.Connection) -> List[sqlite3.Row]:
    """Rows with a proposed name awaiting a human decision."""
    return con.execute(
        "SELECT * FROM files WHERE proposed_name IS NOT NULL AND approved IS NULL "
        "ORDER BY confidence DESC"
    ).fetchall()


def all_proposed(con: sqlite3.Connection) -> List[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM files WHERE proposed_name IS NOT NULL ORDER BY domain, name"
    ).fetchall()


def counts(con: sqlite3.Connection) -> dict:
    total = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    pend = con.execute("SELECT COUNT(*) FROM files WHERE proposed_name IS NOT NULL AND approved IS NULL").fetchone()[0]
    auto = con.execute("SELECT COUNT(*) FROM files WHERE decision='auto_approve'").fetchone()[0]
    skip = con.execute("SELECT COUNT(*) FROM files WHERE decision='skip'").fetchone()[0]
    return {"total": total, "pending": pend, "auto_approve": auto, "skip": skip}
