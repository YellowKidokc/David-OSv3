"""
frequency.py — dependency-free baseline.

Tracks the approval rate for each (domain, ct, status) key and for each tag.
Predicts by blending the key's rate with the mean of its tags' rates, smoothed
toward 0.5 by sample count (Laplace). Always available; a useful floor that the
fancier engines must beat in `compare`.
"""
from __future__ import annotations

import json

import config
from .base import PreferenceEngine
from . import features

_FILE = config.DB_DIR / "pref_frequency.json"


def _rate(d: dict, smooth: float = 2.0) -> float:
    a, n = d.get("approve", 0), d.get("total", 0)
    return (a + smooth * 0.5) / (n + smooth)


class FrequencyEngine(PreferenceEngine):
    name = "frequency"
    MIN_SAMPLES = 4

    def __init__(self):
        super().__init__()
        self.keys: dict = {}     # "dom|ct|st" -> {approve,total}
        self.tags: dict = {}     # tag -> {approve,total}
        self.load()

    def _kstr(self, proposal):
        return "|".join(features.feature_key(proposal))

    def predict(self, proposal: dict) -> float:
        if not self.ready:
            return 0.5
        k = self.keys.get(self._kstr(proposal))
        key_rate = _rate(k) if k else 0.5
        tag_rates = [_rate(self.tags[t]) for t in (proposal.get("tags") or []) if t in self.tags]
        if tag_rates:
            return round(0.6 * key_rate + 0.4 * (sum(tag_rates) / len(tag_rates)), 4)
        return round(key_rate, 4)

    def learn(self, proposal: dict, approved: bool) -> None:
        inc = 1 if approved else 0
        ks = self._kstr(proposal)
        d = self.keys.setdefault(ks, {"approve": 0, "total": 0})
        d["approve"] += inc; d["total"] += 1
        for t in (proposal.get("tags") or []):
            td = self.tags.setdefault(t, {"approve": 0, "total": 0})
            td["approve"] += inc; td["total"] += 1
        self.n_seen += 1

    def save(self) -> None:
        try:
            _FILE.write_text(json.dumps(
                {"keys": self.keys, "tags": self.tags, "n_seen": self.n_seen}),
                encoding="utf-8")
        except Exception:
            pass

    def load(self) -> None:
        if _FILE.exists():
            try:
                s = json.loads(_FILE.read_text(encoding="utf-8"))
                self.keys = s.get("keys", {}); self.tags = s.get("tags", {})
                self.n_seen = s.get("n_seen", 0)
            except Exception:
                pass
