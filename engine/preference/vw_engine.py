"""
vw_engine.py — Vowpal Wabbit online learner.

A second ONLINE engine (besides River) but a different model/optimizer, so the
cascade and compare are meaningful. Logistic loss with a logistic link so
predictions are probabilities. Persistence is best-effort (VW model file).
"""
from __future__ import annotations

import config
from .base import PreferenceEngine
from . import features

try:
    from vowpalwabbit import Workspace
    VW_OK = True
except Exception:
    try:
        from vowpalwabbit import pyvw
        Workspace = pyvw.Workspace          # older API
        VW_OK = True
    except Exception:
        VW_OK = False

_FILE = config.DB_DIR / "pref_vw.model"


class VowpalEngine(PreferenceEngine):
    name = "vowpal_wabbit"
    MIN_SAMPLES = 10

    def __init__(self):
        super().__init__()
        self.vw = None
        self.load()

    @property
    def available(self) -> bool:
        return VW_OK and self.vw is not None

    def _new(self, init_from=None):
        if not VW_OK:
            return None
        args = "--loss_function logistic --link logistic --quiet"
        if init_from:
            args = f"-i {init_from} {args}"
        try:
            return Workspace(args)
        except Exception:
            return None

    def _example(self, proposal: dict, label=None) -> str:
        feats = [k for k, v in features.featurize_binary(proposal).items() if v]
        head = "" if label is None else ("1 " if label == 1 else "-1 ")
        return f"{head}|f " + " ".join(feats)

    def predict(self, proposal: dict) -> float:
        if not self.available or not self.ready:
            return 0.5
        try:
            return round(float(self.vw.predict(self._example(proposal))), 4)
        except Exception:
            return 0.5

    def learn(self, proposal: dict, approved: bool) -> None:
        if not self.available:
            return
        try:
            self.vw.learn(self._example(proposal, 1 if approved else 0))
            self.n_seen += 1
        except Exception:
            pass

    def save(self) -> None:
        if not self.available:
            return
        try:
            self.vw.save(str(_FILE))
        except Exception:
            pass

    def load(self) -> None:
        if _FILE.exists():
            self.vw = self._new(init_from=str(_FILE))
            # n_seen isn't recoverable from the VW model; assume trained if file exists
            if self.vw is not None:
                self.n_seen = max(self.n_seen, self.MIN_SAMPLES)
                return
        self.vw = self._new()
