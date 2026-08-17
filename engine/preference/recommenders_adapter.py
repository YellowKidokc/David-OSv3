"""
recommenders_adapter.py — best-effort bridge to Microsoft Recommenders.

The repo is cloned at D:\\GitHub\\recommenders but the package isn't pip-installed
and its models need heavy deps (lightgbm / tensorflow). This adapter:
  - puts the repo on sys.path so `import recommenders...` works,
  - implements a LightGBM-backed approval predictor (the Recommenders content/CTR
    model family maps cleanly onto our approve/reject task),
  - reports available=False with an install hint when lightgbm is missing, so the
    ensemble simply skips it until you run:  pip install lightgbm recommenders

When lightgbm is present this behaves like sklearn_gbdt but with LightGBM, which
is what recommenders.models.lightgbm uses under the hood.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import config
from .base import PreferenceEngine
from . import features

_REPO = Path(r"D:\GitHub\recommenders")
if _REPO.exists() and str(_REPO) not in sys.path:
    sys.path.append(str(_REPO))   # append, not insert, to avoid shadowing our modules

try:
    import lightgbm as lgb          # the engine recommenders.models.lightgbm wraps
    LGB_OK = True
except Exception:
    LGB_OK = False

# touch the recommenders package only to confirm the path wiring (optional)
try:
    import recommenders  # noqa: F401
    RECO_OK = True
except Exception:
    RECO_OK = False

_FILE = config.DB_DIR / "pref_recommenders.json"
_MAX_HISTORY = 5000


class RecommendersLightGBMEngine(PreferenceEngine):
    name = "recommenders_lightgbm"
    MIN_SAMPLES = 16

    def __init__(self):
        super().__init__()
        self.history: list = []
        self._model = None
        self._vec = None
        self._dirty = True
        self.load()

    @property
    def available(self) -> bool:
        return LGB_OK

    def stats(self) -> dict:
        s = super().stats()
        if not LGB_OK:
            s["hint"] = "pip install lightgbm recommenders"
        s["recommenders_on_path"] = RECO_OK
        return s

    def _refit(self):
        from sklearn.feature_extraction import DictVectorizer
        labels = {h["y"] for h in self.history}
        if not LGB_OK or len(self.history) < self.MIN_SAMPLES or len(labels) < 2:
            self._model = None; self._dirty = False; return
        self._vec = DictVectorizer(sparse=False)
        X = self._vec.fit_transform([features.featurize_binary(h["p"]) for h in self.history])
        y = [h["y"] for h in self.history]
        self._model = lgb.LGBMClassifier(n_estimators=80, num_leaves=15, learning_rate=0.1, verbose=-1)
        self._model.fit(X, y)
        self._dirty = False

    def predict(self, proposal: dict) -> float:
        if not LGB_OK or not self.ready:
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
