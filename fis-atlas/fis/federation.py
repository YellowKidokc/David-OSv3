# fis-op: gov
"""Federation — one central catalog + one search across many territory DBs.

Not one giant database. Each enrolled territory owns a SQLite (a lineage store);
a small central catalog remembers which territories exist; the coordinator runs
the SAME query against each and merges, ORIGIN-TAGGED (T003:F-008142) so local
ids/paths can't collide. Every run records the snapshot it searched and NEVER
claims completeness when a territory was offline.

The AI calls ONE thing — search_all — not query_h / query_d / query_z.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .lineage import Lineage

CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS territories(
  territory_id TEXT PRIMARY KEY, name TEXT, db_path TEXT, kind TEXT DEFAULT 'local',
  enrolled_at TEXT);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Federation:
    def __init__(self, catalog_path: str | Path):
        self.path = Path(catalog_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(CATALOG_SCHEMA)

    def close(self):
        self.conn.commit(); self.conn.close()

    def register_territory(self, territory_id, name, db_path, kind="local"):
        self.conn.execute("INSERT OR REPLACE INTO territories VALUES(?,?,?,?,?)",
                          (territory_id, name, str(db_path), kind, _now()))
        self.conn.commit()

    def territories(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM territories ORDER BY territory_id")]

    def _next_qr(self) -> str:
        r = self.conn.execute("SELECT value FROM meta WHERE key='qr'").fetchone()
        n = int(r["value"]) + 1 if r else 1
        self.conn.execute("INSERT OR REPLACE INTO meta VALUES('qr', ?)", (str(n),))
        self.conn.commit()
        return f"QR-{n:04d}"

    def search_all(self, clue: str, follow: set[str] | None = None, depth: int = 3) -> dict:
        """Run the same trace against every registered territory. Origin-tagged,
        deterministically ordered, with an honest completeness flag."""
        qr = self._next_qr()
        status: dict[str, str] = {}
        results: list[dict] = []
        complete = True
        for t in self.territories():
            tid, db = t["territory_id"], Path(t["db_path"])
            if t["kind"] == "local" and not db.exists():
                status[tid] = "unavailable"; complete = False       # never fake a search
                continue
            try:
                lin = Lineage(db)
                g = lin.trace(clue, follow, depth)
                seq = lin.conn.execute("SELECT COALESCE(MAX(id),0) AS s FROM op_ledger").fetchone()["s"]
                status[tid] = f"seq_{seq}"
                for n in g["nodes"]:
                    results.append({
                        "origin": f"{tid}:{n['object_id']}", "territory": tid,
                        "object_id": n["object_id"], "name": n.get("current_name"),
                        "current_path": n.get("current_path"), "lifecycle": n.get("lifecycle")})
                lin.close()
            except Exception:
                status[tid] = "unavailable"; complete = False
        # deterministic merge: fixed territory then object order
        results.sort(key=lambda r: (r["territory"], r["object_id"]))
        return {"query_run": qr, "clue": clue, "searched_at": _now(),
                "territories": status, "results": results,
                "count": len(results), "complete": complete}
