"""
ensemble.py — run several preference engines together.

Modes (config/engines.yaml):
  blend    weighted average of every available+ready engine's P(approve)
  cascade  first ready engine that is confident (|score-0.5| >= margin) wins;
           otherwise defer to the next engine — i.e. "wire one into another"

Exposes the SAME interface the rest of the app already used (n_seen, MIN_SAMPLES,
predict, learn, should_auto_approve, save, stats) so rename_planner / cli need no
changes. Adds predict_breakdown() (per-engine scores) and backtest() (compare).

Every decision is also appended to a shared JSONL log so any engine can be
rebuilt and `compare` can backtest them all on identical history.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

import config
from .base import PreferenceEngine
from .frequency import FrequencyEngine
from .river_engine import RiverEngine
from .sklearn_gbdt import SklearnGBDTEngine
from .vw_engine import VowpalEngine
from .markov_engine import MarkovEngine
from .recommenders_adapter import RecommendersLightGBMEngine

DECISION_LOG = config.LEDGER_DIR / "pref_decisions.jsonl"
_STATE = config.DB_DIR / "pref_ensemble.json"

_REGISTRY = {
    "frequency": FrequencyEngine,
    "river": RiverEngine,
    "sklearn_gbdt": SklearnGBDTEngine,
    "vowpal_wabbit": VowpalEngine,
    "markov": MarkovEngine,
    "recommenders_lightgbm": RecommendersLightGBMEngine,
}

_CFG_FALLBACK = {
    "mode": "blend",
    "cascade_margin": 0.15,
    "engines": {
        "frequency":             {"enabled": True,  "weight": 0.5},
        "river":                 {"enabled": True,  "weight": 1.0},
        "sklearn_gbdt":          {"enabled": True,  "weight": 1.0},
        "vowpal_wabbit":         {"enabled": True,  "weight": 0.8},
        "markov":                {"enabled": True,  "weight": 0.8},
        "recommenders_lightgbm": {"enabled": False, "weight": 1.0},
    },
}


def _load_cfg() -> dict:
    return config._load_yaml("engines.yaml", _CFG_FALLBACK)


class Ensemble:
    MIN_SAMPLES = 10        # gate used by rename_planner (matches old single-engine)

    def __init__(self):
        cfg = _load_cfg()
        self.mode = cfg.get("mode", "blend")
        self.cascade_margin = float(cfg.get("cascade_margin", 0.15))
        eng_cfg = cfg.get("engines", {})
        self.weights: Dict[str, float] = {}
        self.engines: List[PreferenceEngine] = []
        for name, spec in eng_cfg.items():
            if not spec.get("enabled") or name not in _REGISTRY:
                continue
            try:
                eng = _REGISTRY[name]()
            except Exception:
                continue
            if not eng.available:
                # keep it registered for stats, but it won't vote
                pass
            self.engines.append(eng)
            self.weights[eng.name] = float(spec.get("weight", 1.0))
        self.n_seen = 0
        self._load_state()

    # -- prediction -------------------------------------------------------- #
    def _voters(self) -> List[PreferenceEngine]:
        return [e for e in self.engines if e.available and e.ready]

    def predict_breakdown(self, proposal: dict) -> Dict[str, float]:
        return {e.name: e.predict(proposal) for e in self.engines if e.available}

    def predict(self, proposal: dict) -> float:
        voters = self._voters()
        if not voters:
            return 0.5
        if self.mode == "cascade":
            for e in voters:                       # order = config order
                s = e.predict(proposal)
                if abs(s - 0.5) >= self.cascade_margin:
                    return s
            return voters[0].predict(proposal)
        # blend (default)
        num = sum(self.weights.get(e.name, 1.0) * e.predict(proposal) for e in voters)
        den = sum(self.weights.get(e.name, 1.0) for e in voters)
        return round(num / den, 4) if den else 0.5

    # -- learning ---------------------------------------------------------- #
    def learn(self, proposal: dict, approved: bool, note: str = "") -> None:
        for e in self.engines:
            if e.available:
                try:
                    e.learn(proposal, approved)
                except Exception:
                    pass
        self.n_seen += 1
        rec = {"approved": approved, "note": note,
               "proposal": {k: proposal.get(k) for k in
                            ("proposed_name", "domain_code", "ct_code", "status_code", "tags")}}
        try:
            with open(DECISION_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass
        if self.n_seen % 25 == 0:
            self.save()

    def should_auto_approve(self, proposal: dict, raw_conf: float,
                            base_threshold: float = 0.72) -> Tuple[bool, str]:
        if self.n_seen < self.MIN_SAMPLES:
            return raw_conf >= base_threshold, f"conf={raw_conf:.2f} (no pref data yet, n={self.n_seen})"
        pref = self.predict(proposal)
        if pref < 0.25:
            return False, f"pref={pref:.2f} — pattern repeatedly rejected"
        combined = 0.6 * raw_conf + 0.4 * pref
        return combined >= base_threshold, f"conf={raw_conf:.2f} pref={pref:.2f} combined={combined:.2f}"

    # -- persistence ------------------------------------------------------- #
    def save(self) -> None:
        for e in self.engines:
            try:
                e.save()
            except Exception:
                pass
        try:
            _STATE.write_text(json.dumps({"n_seen": self.n_seen, "mode": self.mode}),
                              encoding="utf-8")
        except Exception:
            pass

    def _load_state(self):
        if _STATE.exists():
            try:
                self.n_seen = json.loads(_STATE.read_text(encoding="utf-8")).get("n_seen", 0)
            except Exception:
                pass

    def stats(self) -> dict:
        return {"mode": self.mode, "n_seen": self.n_seen,
                "weights": self.weights,
                "engines": [e.stats() for e in self.engines]}


# --------------------------------------------------------------------------- #
# Backtest — prequential (predict-then-learn) eval of each engine on the log
# --------------------------------------------------------------------------- #
def backtest(log_path=None) -> List[dict]:
    path = log_path or DECISION_LOG
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
    except Exception:
        return []
    if not rows:
        return []

    results = []
    for name, cls in _REGISTRY.items():
        try:
            eng = cls()
        except Exception:
            continue
        if not eng.available:
            results.append({"engine": name, "available": False, "n": 0})
            continue
        # fresh instance for a fair, history-only contest
        eng.n_seen = 0
        for attr in ("keys", "tags", "history"):
            if hasattr(eng, attr) and isinstance(getattr(eng, attr), (list, dict)):
                getattr(eng, attr).clear()
        correct = warm_correct = warm_n = 0
        logloss = 0.0
        import math
        for r in rows:
            prop, y = r["proposal"], (1 if r["approved"] else 0)
            p = eng.predict(prop)
            ready = eng.ready
            if (p >= 0.5) == bool(y):
                correct += 1
                if ready:
                    warm_correct += 1
            if ready:
                warm_n += 1
            pe = min(max(p, 1e-6), 1 - 1e-6)
            logloss += -(y * math.log(pe) + (1 - y) * math.log(1 - pe))
            eng.learn(prop, bool(y))
        n = len(rows)
        results.append({
            "engine": name, "available": True, "n": n,
            "acc_all": round(correct / n, 3),
            "acc_warm": round(warm_correct / warm_n, 3) if warm_n else None,
            "logloss": round(logloss / n, 3),
        })
    results.sort(key=lambda r: (r.get("acc_warm") or r.get("acc_all") or 0), reverse=True)
    return results


_ensemble = None


def get_ensemble() -> Ensemble:
    global _ensemble
    if _ensemble is None:
        _ensemble = Ensemble()
    return _ensemble
