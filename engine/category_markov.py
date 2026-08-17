"""
category_markov.py — first-order Markov model over file CATEGORIES within a folder.

Files in a folder cluster by subject: a medical folder is mostly medical. So the
category of the previous file in a folder is a real predictor of the next. This
learns P(category_i | category_{i-1}) across all folders, then fills in files the
capability gate left `uncategorized` using their neighbours' run.

Fail-safe preserved: it only ASSIGNS a category to otherwise-uncategorized files
— it never overrides a category the gate actually detected, and the caller still
routes regulated predictions through the (restrictive) registry. Online: it
learns from every scan's observed folder sequences.
"""
from __future__ import annotations

import json

import config

_FILE = config.DB_DIR / "category_markov.json"


class CategoryMarkov:
    def __init__(self):
        self.trans: dict = {}    # prev_cat -> {next_cat: count}
        self.totals: dict = {}   # prev_cat -> total
        self.load()

    def learn_sequence(self, categories: list) -> None:
        for a, b in zip(categories, categories[1:]):
            self.trans.setdefault(a, {})
            self.trans[a][b] = self.trans[a].get(b, 0) + 1
            self.totals[a] = self.totals.get(a, 0) + 1

    def predict_next(self, prev: str):
        """Return (category, probability) for the most likely successor, or (None, 0)."""
        d = self.trans.get(prev)
        if not d or not self.totals.get(prev):
            return None, 0.0
        b = max(d, key=d.get)
        return b, round(d[b] / self.totals[prev], 4)

    def save(self) -> None:
        try:
            _FILE.write_text(json.dumps({"trans": self.trans, "totals": self.totals}),
                             encoding="utf-8")
        except Exception:
            pass

    def load(self) -> None:
        if _FILE.exists():
            try:
                s = json.loads(_FILE.read_text(encoding="utf-8"))
                self.trans = s.get("trans", {}); self.totals = s.get("totals", {})
            except Exception:
                pass
