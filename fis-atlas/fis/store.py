# fis-op: gov
"""SQLite store — the brain (the cache you always wanted).

State lives here, not in scattered JSON. Scanning later means querying this DB
(and the .fisnote layer), not re-walking the disk. mtime-keyed: a re-scan only
re-writes objects whose modified-time changed, so it never slows down.

Tables: folders, objects, clusters, anomalies, questions, rulings, policies,
events (append-only ledger), meta (scan timestamps for staleness).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .model import Atlas

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS folders(
  object_id TEXT PRIMARY KEY, name TEXT, full_path TEXT, rel_path TEXT,
  node_id TEXT, node_type TEXT, parent_node TEXT, folder_class TEXT, risk TEXT,
  purpose TEXT, permissions_json TEXT, symptoms_json TEXT, domains_json TEXT,
  total_descendants INT, total_size INT, last_scanned TEXT);
CREATE TABLE IF NOT EXISTS objects(
  object_id TEXT PRIMARY KEY, name TEXT, ext TEXT, full_path TEXT, parent TEXT,
  is_dir INT, size INT, modified REAL, content_type TEXT, detected_role TEXT,
  sensitivity TEXT, activity TEXT, risk TEXT, proposed_treatment TEXT,
  class_conf REAL, action_conf REAL, domains_json TEXT, clusters_json TEXT,
  evidence_json TEXT, last_scanned TEXT);
CREATE TABLE IF NOT EXISTS clusters(
  cluster_id TEXT PRIMARY KEY, kind TEXT, label TEXT, members_json TEXT, rule TEXT);
CREATE TABLE IF NOT EXISTS anomalies(
  anomaly_id TEXT PRIMARY KEY, family TEXT, observed TEXT, severity TEXT,
  confidence REAL, affected_count INT, evidence_json TEXT);
CREATE TABLE IF NOT EXISTS questions(
  question_id TEXT PRIMARY KEY, anomaly_id TEXT, text TEXT, priority REAL,
  blocking INT, scope TEXT, options_json TEXT);
CREATE TABLE IF NOT EXISTS rulings(
  decision_id TEXT PRIMARY KEY, question_id TEXT, anomaly_id TEXT,
  selected_answer TEXT, scope TEXT, applies_to_pattern TEXT, timestamp TEXT);
CREATE TABLE IF NOT EXISTS policies(
  policy_id TEXT PRIMARY KEY, from_decision TEXT, family TEXT, pattern TEXT,
  verdict TEXT, scope TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, subject TEXT,
  payload_json TEXT, ts TEXT);
CREATE INDEX IF NOT EXISTS idx_obj_parent ON objects(parent);
CREATE INDEX IF NOT EXISTS idx_obj_ct ON objects(content_type);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.commit()
        self.conn.close()

    def event(self, kind, subject, payload=None):
        self.conn.execute("INSERT INTO events(kind,subject,payload_json,ts) VALUES(?,?,?,?)",
                          (kind, subject, json.dumps(payload or {}), _now()))

    def save_atlas(self, atlas: Atlas) -> dict:
        """Upsert folders/objects/clusters. mtime-keyed: unchanged objects skip re-write."""
        c = self.conn
        written, skipped = 0, 0
        existing = {r["object_id"]: r["modified"]
                    for r in c.execute("SELECT object_id, modified FROM objects")}
        for f in atlas.folders.values():
            c.execute("""INSERT OR REPLACE INTO folders VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f.object_id, f.name, f.full_path, f.rel_path, f.node_id, f.node_type,
                 f.parent_node, f.folder_class, f.risk, f.purpose,
                 json.dumps(f.permissions), json.dumps(f.symptoms), json.dumps(f.domains),
                 f.total_descendants, f.total_size, _now()))
        for o in atlas.objects.values():
            if existing.get(o.object_id) == o.modified:
                skipped += 1
                continue
            c.execute("""INSERT OR REPLACE INTO objects VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (o.object_id, o.name, o.ext, o.full_path, o.parent, int(o.is_dir),
                 o.size, o.modified, o.content_type, o.detected_role, o.sensitivity,
                 o.activity, o.risk, o.proposed_treatment, o.class_confidence,
                 o.action_confidence, json.dumps(o.domains), json.dumps(o.clusters),
                 json.dumps(o.evidence.reasons), _now()))
            written += 1
        for cl in atlas.clusters:
            c.execute("INSERT OR REPLACE INTO clusters VALUES(?,?,?,?,?)",
                      (cl.cluster_id, cl.kind, cl.label, json.dumps(cl.members), cl.proposed_rule))
        c.execute("INSERT OR REPLACE INTO meta VALUES('last_scan_root', ?)", (atlas.root,))
        c.execute("INSERT OR REPLACE INTO meta VALUES('last_scan_at', ?)", (_now(),))
        self.event("atlas_saved", atlas.root, {"written": written, "skipped": skipped})
        self.conn.commit()
        return {"objects_written": written, "objects_unchanged": skipped,
                "folders": len(atlas.folders)}

    def save_report(self, model: dict):
        c = self.conn
        for a in model.get("_anomalies", []):
            pass
        for q in model.get("open_questions", []):
            c.execute("INSERT OR REPLACE INTO questions VALUES(?,?,?,?,?,?,?)",
                      (q["question_id"], q.get("anomaly_id", ""), q["question"], q["priority"],
                       int(q["blocking"]), q["ruling_scope"], json.dumps(q["options"])))
        self.conn.commit()

    # --- reads that make "scan the DB, not the disk" real ---
    def search(self, term: str, limit: int = 50):
        rows = self.conn.execute(
            "SELECT name, full_path, content_type FROM objects WHERE name LIKE ? LIMIT ?",
            (f"%{term}%", limit))
        return [dict(r) for r in rows]

    def counts(self) -> dict:
        return {t: self.conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
                for t in ("folders", "objects", "clusters", "questions", "events")}
