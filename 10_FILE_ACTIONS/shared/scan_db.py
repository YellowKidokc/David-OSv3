"""scan_db.py — SQLite staging layer for deep_identify results.

Everything lands here first. Reports, inbox, GUI, and prediction engine all read from this.
Files only move after the database says it's right.

Tables:
  scans          — one row per scan run (target, timestamp, stats)
  cards          — one row per file (all FileCard fields + attention terms)
  families       — one row per discovered family
  family_members — join table: which cards belong to which families
  attention      — per-document attention vectors (top 30 terms + law signals)
  fingerprints   — document identity hashes (steganographic IDs)
  decisions      — every approve/reject from the prediction GUI feeds back here

Usage:
    from scan_db import ScanDB
    db = ScanDB("path/to/scans.db")
    db.ingest_report("runs/ftp_final/deep_identify.json")
    db.ingest_attention("runs/ftp_final/attention/")
    cards = db.query_cards(domain="theophysics", doc_type="paper", min_confidence=0.6)
    family = db.get_family("FAM-0737f58e")
    db.record_decision(card_path, "approved", actor="David")
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    scan_id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    files_seen INTEGER,
    files_scanned INTEGER,
    families_found INTEGER,
    orphans INTEGER,
    avg_confidence REAL,
    stats_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    path TEXT NOT NULL,
    scan_id TEXT NOT NULL,
    name TEXT,
    extension TEXT,
    size_bytes INTEGER,
    modified_at TEXT,
    sha256 TEXT,
    container_type TEXT,
    is_protected INTEGER,
    can_move INTEGER,
    can_rename INTEGER,
    file_kind TEXT,
    domain TEXT,
    domain_confidence REAL,
    doc_type TEXT,
    doc_type_confidence REAL,
    content_length INTEGER,
    has_yaml_frontmatter INTEGER,
    has_sections INTEGER,
    section_count INTEGER,
    family_id TEXT,
    family_name TEXT,
    position_in_family INTEGER,
    position_source TEXT,
    identity_confidence REAL,
    relationship_strength REAL,
    orphan_probability REAL,
    extraction_status TEXT,
    content_tokens_json TEXT,
    references_to_json TEXT,
    referenced_by_json TEXT,
    ambiguous_refs_json TEXT,
    fingerprint TEXT,
    PRIMARY KEY (path, scan_id)
);

CREATE TABLE IF NOT EXISTS families (
    family_id TEXT NOT NULL,
    scan_id TEXT NOT NULL,
    family_name TEXT,
    member_count INTEGER,
    confidence REAL,
    is_series INTEGER,
    completeness REAL,
    gaps_json TEXT,
    competing_json TEXT,
    domain TEXT,
    evidence_json TEXT,
    PRIMARY KEY (family_id, scan_id)
);

CREATE TABLE IF NOT EXISTS family_members (
    family_id TEXT NOT NULL,
    scan_id TEXT NOT NULL,
    path TEXT NOT NULL,
    position INTEGER,
    PRIMARY KEY (family_id, scan_id, path)
);

CREATE TABLE IF NOT EXISTS attention (
    path TEXT NOT NULL,
    scan_id TEXT NOT NULL,
    terms_json TEXT,
    law_signals_json TEXT,
    top_law TEXT,
    vector_norm REAL,
    PRIMARY KEY (path, scan_id)
);

CREATE TABLE IF NOT EXISTS fingerprints (
    path TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    method TEXT NOT NULL,
    created_at TEXT NOT NULL,
    verified_at TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    scan_id TEXT,
    family_id TEXT,
    decision TEXT NOT NULL,
    actor TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cards_domain ON cards(scan_id, domain);
CREATE INDEX IF NOT EXISTS ix_cards_doctype ON cards(scan_id, doc_type);
CREATE INDEX IF NOT EXISTS ix_cards_family ON cards(scan_id, family_id);
CREATE INDEX IF NOT EXISTS ix_cards_confidence ON cards(scan_id, identity_confidence);
CREATE INDEX IF NOT EXISTS ix_families_scan ON families(scan_id);
CREATE INDEX IF NOT EXISTS ix_decisions_path ON decisions(path);
"""


class ScanDB:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def ingest_report(self, report_path: str | Path) -> str:
        """Load a deep_identify.json report into the database. Returns scan_id."""
        data = json.loads(Path(report_path).read_text(encoding="utf-8"))
        stats = data["stats"]
        scan_id = hashlib.sha1(
            (stats["target"] + stats.get("completed_at", "")).encode()
        ).hexdigest()[:12]
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            "INSERT OR REPLACE INTO scans VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (scan_id, stats["target"], stats.get("started_at"), stats.get("completed_at"),
             stats.get("files_seen"), stats.get("files_scanned"), stats.get("families_found"),
             stats.get("orphans"), stats.get("avg_identity_confidence"),
             json.dumps(stats, ensure_ascii=False), now))

        for card in data.get("cards", []):
            self.conn.execute(
                "INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (card["path"], scan_id, card["name"], card["extension"], card["size_bytes"],
                 card["modified_at"], card["sha256"], card["container_type"],
                 int(card["is_protected"]), int(card["can_move"]), int(card["can_rename"]),
                 card["file_kind"], card["domain"], card["domain_confidence"],
                 card["doc_type"], card["doc_type_confidence"], card["content_length"],
                 int(card["has_yaml_frontmatter"]), int(card["has_sections"]), card["section_count"],
                 card["family_id"], card["family_name"], card["position_in_family"],
                 card["position_source"], card["identity_confidence"],
                 card["relationship_strength"], card["orphan_probability"],
                 card.get("extraction_status", ""),
                 json.dumps(card.get("content_tokens", [])[:30]),
                 json.dumps(card.get("references_to", [])),
                 json.dumps(card.get("referenced_by", [])),
                 json.dumps(card.get("ambiguous_refs", [])),
                 self._fingerprint(card["path"], card.get("sha256", ""))))

        for fam in data.get("families", []):
            self.conn.execute(
                "INSERT OR REPLACE INTO families VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (fam["family_id"], scan_id, fam["family_name"], fam["member_count"],
                 fam["confidence"], int(fam["is_series"]), fam["completeness"],
                 json.dumps(fam["gaps"]), json.dumps(fam.get("competing_versions", {})),
                 fam["domain"], json.dumps(fam["evidence"])))
            for member in fam["members"]:
                pos = next((c["position_in_family"] for c in data["cards"] if c["path"] == member), -1)
                self.conn.execute(
                    "INSERT OR REPLACE INTO family_members VALUES (?,?,?,?)",
                    (fam["family_id"], scan_id, member, pos))

        self.conn.commit()
        return scan_id

    def ingest_attention(self, attention_dir: str | Path, scan_id: str = ""):
        """Load attention_vectors.json into the database."""
        vpath = Path(attention_dir) / "attention_vectors.json"
        if not vpath.exists():
            return
        vecs = json.loads(vpath.read_text(encoding="utf-8"))
        for path, vec in vecs.items():
            self.conn.execute(
                "INSERT OR REPLACE INTO attention VALUES (?,?,?,?,?,?)",
                (path, scan_id, json.dumps(vec["terms"]),
                 json.dumps(vec["law_signals"]), vec["top_law"], vec["norm"]))
        self.conn.commit()

    def _fingerprint(self, path: str, sha256: str) -> str:
        """Generate a deterministic document fingerprint."""
        # Method: SHA-256 of (path_stem + file_hash), truncated to 8 hex chars
        # This is the basic version; the salted version uses a user-provided key
        stem = Path(path).stem.lower()
        raw = hashlib.sha256(f"{stem}:{sha256}".encode()).hexdigest()[:8]
        self.conn.execute(
            "INSERT OR IGNORE INTO fingerprints VALUES (?,?,?,?,NULL)",
            (path, raw, "stem_hash_v1", datetime.now(timezone.utc).isoformat()))
        return raw

    def query_cards(self, scan_id: str = "", domain: str = "", doc_type: str = "",
                    min_confidence: float = 0.0, family_id: str = "",
                    orphans_only: bool = False, limit: int = 500) -> list[dict]:
        """Query cards with filters."""
        where, params = ["1=1"], []
        if scan_id:
            where.append("scan_id=?"); params.append(scan_id)
        else:
            where.append("scan_id=(SELECT scan_id FROM scans ORDER BY created_at DESC LIMIT 1)")
        if domain:
            where.append("domain=?"); params.append(domain)
        if doc_type:
            where.append("doc_type=?"); params.append(doc_type)
        if min_confidence > 0:
            where.append("identity_confidence>=?"); params.append(min_confidence)
        if family_id:
            where.append("family_id=?"); params.append(family_id)
        if orphans_only:
            where.append("orphan_probability>0.5 AND file_kind='document'")
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM cards WHERE {' AND '.join(where)} ORDER BY identity_confidence DESC LIMIT ?",
            params).fetchall()
        return [dict(r) for r in rows]

    def get_family(self, family_id: str, scan_id: str = "") -> Optional[dict]:
        if not scan_id:
            row = self.conn.execute(
                "SELECT * FROM families WHERE family_id=? ORDER BY rowid DESC LIMIT 1",
                (family_id,)).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM families WHERE family_id=? AND scan_id=?",
                (family_id, scan_id)).fetchone()
        return dict(row) if row else None

    def record_decision(self, path: str, decision: str, actor: str = "David",
                        scan_id: str = "", family_id: str = "", note: str = ""):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO decisions (path, scan_id, family_id, decision, actor, note, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (path, scan_id, family_id, decision, actor, note, now))
        self.conn.commit()

    def decision_history(self, path: str = "", limit: int = 100) -> list[dict]:
        if path:
            rows = self.conn.execute(
                "SELECT * FROM decisions WHERE path=? ORDER BY created_at DESC LIMIT ?",
                (path, limit)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def latest_scan(self) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM scans ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def stats(self) -> dict:
        """Quick summary of what's in the database."""
        s = self.conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        c = self.conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        f = self.conn.execute("SELECT COUNT(*) FROM families").fetchone()[0]
        d = self.conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        a = self.conn.execute("SELECT COUNT(*) FROM attention").fetchone()[0]
        fp = self.conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0]
        return {"scans": s, "cards": c, "families": f, "decisions": d,
                "attention": a, "fingerprints": fp}
