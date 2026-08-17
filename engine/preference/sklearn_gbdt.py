"""
sklearn_gbdt.py — batch gradient-boosted trees (sklearn).

A different algorithm family from the linear engines, so `compare` is a real
contest. Keeps the decision history and lazily refits when dirty + ready. Stands
in for the heavier LightGBM/Recommenders models until those deps are installed.
"""
from __future__ import annotations

import json

import config
from .base import PreferenceEngine
from . import features

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.feature_extraction import DictVectorizer
    SK_OK = True
except Exception:
    SK_OK = False

_FILE = config.DB_DIR / "pref_sklearn.json"
_MAX_HISTORY = 5000


class SklearnGBDTEngine(PreferenceEngine):
    name = "sklearn_gbdt"
    MIN_SAMPLES = 12

    def __init__(self):
        super().__init__()
        self.history: list = []     # [{"p": proposal, "y": 0/1}]
        self._model = None
        self._vec = None
        self._dirty = True
        self.load()

    @property
    def available(self) -> bool:
        return SK_OK

    def _refit(self):
        labels = {h["y"] for h in self.history}
        if not SK_OK or len(self.history) < self.MIN_SAMPLES or len(labels) < 2:
            self._model = None
            self._dirty = False
            return
        X = [features.featurize_binary(h["p"]) for h in self.history]
        y = [h["y"] for h in self.history]
        self._vec = DictVectorizer(sparse=False)
        Xv = self._vec.fit_transform(X)
        self._model = GradientBoostingClassifier(n_estimators=60, max_depth=3, learning_rate=0.1)
        self._model.fit(Xv, y)
        self._dirty = False

    def predict(self, proposal: dict) -> float:
        if not SK_OK or not self.ready:
            return 0.5
        if self._dirty:
            self._refit()
        if not self._model:
            return 0.5
        try:
            Xv = self._vec.transform([features.featurize_binary(proposal)])
            idx = list(self._model.classes_).index(1)
            return round(float(self._model.predict_proba(Xv)[0][idx]), 4)
        except Exception:
            return 0.5

    def learn(self, proposal: dict, approved: bool) -> None:
        self.history.append({"p": {k: proposal.get(k) for k in
                                   ("domain_code", "ct_code", "status_code", "tags")},
                             "y": 1 if approved else 0})
        self.history = self.history[-_MAX_HISTORY:]
        self.n_seen += 1
        self._dirty = True

    def save(self) -> None:
        try:
            _FILE.write_text(json.dumps({"history": self.history, "n_seen": self.n_seen}),
                             encoding="utf-8")
        except Exception:
            pass

    def load(self) -> None:
        if _FILE.exists():
            try:
                s = json.loads(_FILE.read_text(encoding="utf-8"))
                self.history = s.get("history", []); self.n_seen = s.get("n_seen", 0)
                self._dirty = True
            except Exception:
                pass
