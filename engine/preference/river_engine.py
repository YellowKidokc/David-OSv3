"""
river_engine.py — online logistic regression (River SGD).

The original FIS engine: updates on every decision, no batch retraining. Moved
here behind the common interface so it sits alongside the alternatives.
"""
from __future__ import annotations

import pickle

import config
from .base import PreferenceEngine
from . import features

try:
    from river import linear_model, optim
    RIVER_OK = True
except Exception:
    RIVER_OK = False

_FILE = config.DB_DIR / "pref_river.pkl"


class RiverEngine(PreferenceEngine):
    name = "river"
    MIN_SAMPLES = 10

    def __init__(self):
        super().__init__()
        self.model = None
        self.load()

    @property
    def available(self) -> bool:
        return RIVER_OK

    def _new(self):
        return linear_model.LogisticRegression(optimizer=optim.SGD(lr=0.05)) if RIVER_OK else None

    def predict(self, proposal: dict) -> float:
        if not self.model or not self.ready:
            return 0.5
        try:
            return float(self.model.predict_proba_one(features.featurize_binary(proposal)).get(1, 0.5))
        except Exception:
            return 0.5

    def learn(self, proposal: dict, approved: bool) -> None:
        if not RIVER_OK:
            return
        if self.model is None:
            self.model = self._new()
        self.model.learn_one(features.featurize_binary(proposal), 1 if approved else 0)
        self.n_seen += 1

    def save(self) -> None:
        if not self.model:
            return
        try:
            with open(_FILE, "wb") as f:
                pickle.dump({"model": self.model, "n_seen": self.n_seen}, f)
        except Exception:
            pass

    def load(self) -> None:
        if _FILE.exists():
            try:
                with open(_FILE, "rb") as f:
                    s = pickle.load(f)
                self.model = s["model"]; self.n_seen = s.get("n_seen", 0)
                return
            except Exception:
                pass
        self.model = self._new()
