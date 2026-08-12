"""Central identity + lineage registry — the load-bearing store.

A path is a file's current ADDRESS, not its identity. The registry assigns a
stable object_id and remembers the file across rename/move/copy/convert. Every
operation is a lineage EDGE, so "trace the roots" is a graph query. Project
membership is independent of location. The .fisnote becomes an optional VIEW
onto these records, never their owner.

    registry     stable identity + current location
    ledger       every operation against an object_id
    graph        copies, conversions, versions, projects, references
    project       stable membership regardless of where files live

Operation → identity semantics:
    move/rename/archive = SAME object (new address/name/state)
    copy/convert        = NEW object descended from a parent
    combine             = NEW object, multiple parents
    split               = several NEW objects, one parent

Relationships carry an evidence TIER — recorded (from the ledger) vs
verified/inferred/possible (reconstructed) — and inferred is never shown as fact.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

TIERS = ("recorded", "verified", "inferred", "possible")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS objects(
  object_id TEXT PRIMARY KEY, kind TEXT, ext TEXT, sha256 TEXT, phash INTEGER,
  original_name TEXT, current_name TEXT, current_path TEXT, discovered_at TEXT,
  lifecycle TEXT DEFAULT 'active');
CREATE TABLE IF NOT EXISTS lineage(
  id INTEGER PRIMARY KEY AUTOINCREMENT, parent TEXT, child TEXT,
  relationship TEXT, tier TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS op_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT, object_id TEXT, operation TEXT,
  from_path TEXT, to_path TEXT, process TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS projects(project_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS project_members(
  project_id TEXT, object_id TEXT, PRIMARY KEY(project_id, object_id));
CREATE INDEX IF NOT EXISTS idx_lineage_parent ON lineage(parent);
CREATE INDEX IF NOT EXISTS idx_lineage_child ON lineage(child);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Lineage:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.commit(); self.conn.close()

    def _next_id(self) -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key='counter'").fetchone()
        n = int(row["value"]) + 1 if row else 1
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES('counter', ?)", (str(n),))
        return f"F-{n:06d}"

    # ---- register + same-object ops ----
    def register(self, *, kind, ext, path, name=None, sha256=None, phash=None,
                 project=None) -> str:
        oid = self._next_id()
        name = name or Path(path).name
        self.conn.execute(
            "INSERT INTO objects(object_id,kind,ext,sha256,phash,original_name,"
            "current_name,current_path,discovered_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (oid, kind, ext, sha256, phash, name, name, path, _now()))
        self._ledger(oid, "discover", None, path)
        if project:
            self.add_to_project(project, project, [oid])
        self.conn.commit()
        return oid

    def move(self, object_id, to_path, process=None):
        cur = self._path(object_id)
        self.conn.execute("UPDATE objects SET current_path=? WHERE object_id=?", (to_path, object_id))
        self._ledger(object_id, "move", cur, to_path, process); self.conn.commit()

    def rename(self, object_id, new_name, process=None):
        cur = self._path(object_id)
        new_path = str(Path(cur).with_name(new_name)) if cur else new_name
        self.conn.execute("UPDATE objects SET current_name=?,current_path=? WHERE object_id=?",
                          (new_name, new_path, object_id))
        self._ledger(object_id, "rename", cur, new_path, process); self.conn.commit()

    def archive(self, object_id, to_path, process=None):
        cur = self._path(object_id)
        self.conn.execute("UPDATE objects SET current_path=?,lifecycle='archived' WHERE object_id=?",
                          (to_path, object_id))
        self._ledger(object_id, "archive", cur, to_path, process); self.conn.commit()

    # ---- new-object ops (descendants) ----
    def copy(self, source_id, to_path, name=None):
        return self._derive(source_id, "copied_from", to_path, name, op="copy")

    def convert(self, source_id, to_path, ext, name=None):
        child = self._derive(source_id, "converted_from", to_path, name, op="convert")
        self.conn.execute("UPDATE objects SET ext=? WHERE object_id=?", (ext, child))
        self.conn.commit()
        return child

    def combine(self, parent_ids, to_path, kind="combined", name=None):
        child = self.register(kind=kind, ext=Path(to_path).suffix.lstrip("."),
                              path=to_path, name=name)
        for p in parent_ids:
            self._edge(p, child, "combined_from", "recorded")
        self.conn.commit()
        return child

    def split(self, source_id, to_paths):
        kids = []
        for tp in to_paths:
            k = self.register(kind=self._kind(source_id), ext=Path(tp).suffix.lstrip("."), path=tp)
            self._edge(source_id, k, "split_from", "recorded")
            kids.append(k)
        self.conn.commit()
        return kids

    def _derive(self, source_id, rel, to_path, name, op):
        child = self.register(kind=self._kind(source_id),
                              ext=Path(to_path).suffix.lstrip("."), path=to_path, name=name)
        self._edge(source_id, child, rel, "recorded")
        self._ledger(child, op, self._path(source_id), to_path)
        self.conn.commit()
        return child

    # ---- reconstructed relationships (never 'recorded') ----
    def relate(self, parent, child, relationship, tier="inferred"):
        assert tier in TIERS and tier != "recorded", "reconstructed edges are not 'recorded'"
        self._edge(parent, child, relationship, tier); self.conn.commit()

    # ---- projects ----
    def add_to_project(self, project_id, name, object_ids):
        self.conn.execute("INSERT OR IGNORE INTO projects VALUES(?,?)", (project_id, name))
        for oid in object_ids:
            self.conn.execute("INSERT OR IGNORE INTO project_members VALUES(?,?)", (project_id, oid))
        self.conn.commit()

    def members(self, project_id) -> list[dict]:
        rows = self.conn.execute(
            "SELECT o.object_id,o.current_path,o.lifecycle FROM project_members m "
            "JOIN objects o ON o.object_id=m.object_id WHERE m.project_id=?", (project_id,))
        return [dict(r) for r in rows]

    # ---- TRACE (the search addition) ----
    def trace(self, clue: str, follow: set[str] | None = None, depth: int = 3) -> dict:
        """Anchor on a clue, follow lineage/project edges N levels. Returns a
        graph with every edge's evidence tier — inferred is never shown as fact."""
        follow = follow or {"project", "rename", "move", "copy", "convert", "reference"}
        anchors = self._anchor(clue)
        seen, edges = set(anchors), []
        frontier = set(anchors)
        for _ in range(depth):
            nxt = set()
            for oid in frontier:
                for row in self.conn.execute(
                        "SELECT parent,child,relationship,tier FROM lineage WHERE parent=? OR child=?",
                        (oid, oid)):
                    edges.append(dict(row))
                    for other in (row["parent"], row["child"]):
                        if other and other not in seen:
                            seen.add(other); nxt.add(other)
            frontier = nxt
            if not frontier:
                break
        nodes = [dict(self.conn.execute("SELECT object_id,current_path,current_name,lifecycle "
                                        "FROM objects WHERE object_id=?", (n,)).fetchone() or {})
                 for n in seen]
        return {"clue": clue, "anchors": anchors, "nodes": [n for n in nodes if n],
                "edges": edges, "follow": sorted(follow)}

    def _anchor(self, clue: str) -> list[str]:
        c = f"%{clue}%"
        rows = self.conn.execute(
            "SELECT DISTINCT object_id FROM objects WHERE current_path LIKE ? "
            "OR current_name LIKE ? OR original_name LIKE ?", (c, c, c)).fetchall()
        ids = {r["object_id"] for r in rows}
        for r in self.conn.execute(
                "SELECT object_id FROM project_members WHERE project_id LIKE ?", (c,)):
            ids.add(r["object_id"])
        return sorted(ids)

    # ---- helpers ----
    def _edge(self, parent, child, rel, tier):
        self.conn.execute("INSERT INTO lineage(parent,child,relationship,tier,ts) VALUES(?,?,?,?,?)",
                          (parent, child, rel, tier, _now()))

    def _ledger(self, oid, op, frm, to, process=None):
        self.conn.execute("INSERT INTO op_ledger(object_id,operation,from_path,to_path,process,ts) "
                          "VALUES(?,?,?,?,?,?)", (oid, op, frm, to, process, _now()))

    def _path(self, oid):
        r = self.conn.execute("SELECT current_path FROM objects WHERE object_id=?", (oid,)).fetchone()
        return r["current_path"] if r else None

    def _kind(self, oid):
        r = self.conn.execute("SELECT kind FROM objects WHERE object_id=?", (oid,)).fetchone()
        return r["kind"] if r else "unknown"
