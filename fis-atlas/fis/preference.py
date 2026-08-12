"""Preference learning (lrn) — learns YOU from approvals.

Two learners, per the ruling:
  1. Contextual approval counts (PRIMARY) — smoothed approval rate per
     (file_family, source_context, action, target). Small, explainable, updates
     immediately, no training infra.
        P(approve) = (approvals + 1) / (approvals + rejections + 2)
  2. Markov chains (SECONDARY) — ride on the approval stream:
       * action sequences   (after 'scan' you usually 'classify')
       * name-token order    (learns your naming STYLE from approved names)

Both persist in SQLite so they survive restarts and get smarter per click.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pref_counts(
  file_family TEXT, source_context TEXT, action TEXT, target TEXT,
  approvals INT DEFAULT 0, rejections INT DEFAULT 0,
  PRIMARY KEY(file_family, source_context, action, target));
CREATE TABLE IF NOT EXISTS markov_actions(
  prev TEXT, next TEXT, count INT DEFAULT 0, PRIMARY KEY(prev, next));
CREATE TABLE IF NOT EXISTS markov_tokens(
  prev TEXT, next TEXT, count INT DEFAULT 0, PRIMARY KEY(prev, next));
"""


class Preferences:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.commit(); self.conn.close()

    # ---- 1. contextual approval counts (primary) ----
    def record(self, file_family, source_context, action, target, approved: bool):
        col = "approvals" if approved else "rejections"
        self.conn.execute(
            "INSERT INTO pref_counts(file_family,source_context,action,target,"
            f"{col}) VALUES(?,?,?,?,1) "
            "ON CONFLICT(file_family,source_context,action,target) "
            f"DO UPDATE SET {col}={col}+1",
            (file_family, source_context, action, target))
        self.conn.commit()

    def approval_rate(self, file_family, source_context, action, target) -> float:
        r = self.conn.execute(
            "SELECT approvals,rejections FROM pref_counts WHERE "
            "file_family=? AND source_context=? AND action=? AND target=?",
            (file_family, source_context, action, target)).fetchone()
        a, j = (r["approvals"], r["rejections"]) if r else (0, 0)
        return (a + 1) / (a + j + 2)                     # Laplace-smoothed

    def best_target(self, file_family, source_context, action):
        rows = self.conn.execute(
            "SELECT target,approvals,rejections FROM pref_counts WHERE "
            "file_family=? AND source_context=? AND action=?",
            (file_family, source_context, action)).fetchall()
        if not rows:
            return None
        scored = [(r["target"], (r["approvals"] + 1) / (r["approvals"] + r["rejections"] + 2))
                  for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0]                                 # (target, rate)

    # ---- 2. Markov on approvals (secondary) ----
    def record_action_sequence(self, prev: str, nxt: str):
        self._bump("markov_actions", prev, nxt)

    def predict_next_action(self, prev: str):
        rows = self.conn.execute(
            "SELECT next,count FROM markov_actions WHERE prev=? ORDER BY count DESC", (prev,)).fetchall()
        return rows[0]["next"] if rows else None

    def learn_approved_name(self, name: str):
        toks = self._tok(name)
        for a, b in zip(["^"] + toks, toks + ["$"]):
            self._bump("markov_tokens", a, b)

    def name_style_score(self, name: str) -> float:
        """Likelihood a name matches the approved style (0..1-ish, higher = more 'you')."""
        toks = ["^"] + self._tok(name) + ["$"]
        if len(toks) < 2:
            return 0.0
        total, hit = 0, 0.0
        for a, b in zip(toks, toks[1:]):
            r = self.conn.execute("SELECT count FROM markov_tokens WHERE prev=? AND next=?",
                                  (a, b)).fetchone()
            seen = self.conn.execute("SELECT SUM(count) s FROM markov_tokens WHERE prev=?",
                                     (a,)).fetchone()["s"] or 0
            hit += ((r["count"] if r else 0) + 1) / (seen + 2)
            total += 1
        return round(hit / total, 3)

    def _bump(self, table, prev, nxt):
        self.conn.execute(
            f"INSERT INTO {table}(prev,next,count) VALUES(?,?,1) "
            "ON CONFLICT(prev,next) DO UPDATE SET count=count+1", (prev, nxt))
        self.conn.commit()

    @staticmethod
    def _tok(name: str):
        stem = re.sub(r"\.\w+$", "", name)
        return [t for t in re.split(r"[^a-zA-Z0-9]+", stem.lower()) if t]
