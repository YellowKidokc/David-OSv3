"""Escalation ladder (David's rule): tools first, model last.

The model does NOT engage on the first sign of trouble. Deterministic tools +
the .dec rules try to resolve an issue. Only after the user has tried a few
times WITHOUT resolution does the model become available to talk to them.

    attempt -> attempt -> attempt (unresolved) -> MODEL MAY ENGAGE

Attempts are logged (append-only) so the decision is auditable, not vibes.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_key TEXT, tool TEXT,
  resolved INT, ts TEXT);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Escalation:
    def __init__(self, path: str | Path, max_self_serve: int = 3):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.max_self_serve = max_self_serve

    def close(self):
        self.conn.commit(); self.conn.close()

    def note_attempt(self, issue_key: str, tool: str, resolved: bool):
        self.conn.execute("INSERT INTO attempts(issue_key,tool,resolved,ts) VALUES(?,?,?,?)",
                          (issue_key, tool, int(resolved), _now()))
        self.conn.commit()

    def unresolved_attempts(self, issue_key: str) -> int:
        # attempts since the last resolution
        rows = self.conn.execute(
            "SELECT resolved FROM attempts WHERE issue_key=? ORDER BY id", (issue_key,)).fetchall()
        count = 0
        for r in rows:
            if r["resolved"]:
                count = 0
            else:
                count += 1
        return count

    def should_engage_model(self, issue_key: str) -> bool:
        """Model becomes available ONLY after max_self_serve unresolved tries."""
        return self.unresolved_attempts(issue_key) >= self.max_self_serve

    def state(self, issue_key: str) -> dict:
        n = self.unresolved_attempts(issue_key)
        return {"issue_key": issue_key, "unresolved_attempts": n,
                "threshold": self.max_self_serve,
                "model_available": n >= self.max_self_serve,
                "remaining_before_model": max(0, self.max_self_serve - n)}
