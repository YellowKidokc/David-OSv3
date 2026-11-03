"""
fis_preference_engine.py — Online learning preference engine for FIS naming.

Uses River (online ML) so every approve/reject immediately updates the model.
No batch retraining. No restarts. Learns from the first decision.

Model: Logistic Regression over one-hot features (domain, content type, status, tags).
Stored at FIS_DIR/fis_pref_model.pkl — survives restarts.

Usage:
    engine = PreferenceEngine()
    engine.learn(proposal, approved=True)      # called on every user decision
    p = engine.predict(proposal)               # 0.0–1.0 probability of approval
    engine.save()
"""

import json
import logging
import os
import pickle
from pathlib import Path

try:
    from river import linear_model, optim
    RIVER_OK = True
except ImportError:
    RIVER_OK = False

FIS_DIR    = Path(__file__).resolve().parent
MODEL_FILE = FIS_DIR / "fis_pref_model.pkl"
LOG_FILE   = FIS_DIR / "fis_pref_log.jsonl"

# ---------------------------------------------------------------------------
# Feature builder
# The model sees a flat dict of binary features derived from a naming proposal.
# ---------------------------------------------------------------------------

# All known domain codes, ct codes, status codes, tag codes
_DOMAINS  = ["TH","DT","CD","PH","CS","EP","MT","MR","IF","MD","TR","LG","KG","EV","AI","GN"]
_CTS      = ["COD","DOC","DAT","NOT","CFG","PRF","PAP","SRM","IMG","VID","AUD","BIN"]
_STATUSES = ["AC","DR","FN","AR","RV","WP"]
_TAGS     = [
    "CSN","COH","FSL","CHI","GRC","MRL","ENT","FTH","REL","QNT","KNW","TMP","LGS",
    "L01","L02","L03","L04","L05","L06","L07","L08","L09","L10",
    "PMK","BKT","WTL","RSK","STG","SIG","PNL","OPT","SCN","JRN","CHT",
    "DMN","SRV","CLF","DBS","CFG","AHK","WEB","INS","WCH",
    "STA","AUD","CLM","AXM","CRP","GRP","PRF",
    "SCR","THM","REC","EXP","GN",
]

def _featurize(proposal: dict) -> dict:
    """
    Convert a naming proposal into a flat binary feature dict for River.
    Example output:
        {"dom_TH": 1, "ct_COD": 1, "st_AC": 1, "tag_CSN": 1, "tag_COH": 1, ...}
    """
    feats: dict = {}
    dom = proposal.get("domain_code", "GN")
    ct  = proposal.get("ct_code",     "DOC")
    st  = proposal.get("status_code", "AC")

    for d in _DOMAINS:
        feats[f"dom_{d}"] = 1 if dom == d else 0
    for c in _CTS:
        feats[f"ct_{c}"] = 1 if ct == c else 0
    for s in _STATUSES:
        feats[f"st_{s}"] = 1 if st == s else 0

    tags = set(proposal.get("tags") or [])
    for t in _TAGS:
        feats[f"tag_{t}"] = 1 if t in tags else 0

    return feats


# ---------------------------------------------------------------------------
# Preference engine
# ---------------------------------------------------------------------------

class PreferenceEngine:
    """
    Wraps a River LogisticRegression with load/save and a simple fallback
    when there's not enough data yet (< MIN_SAMPLES decisions logged).
    """

    MIN_SAMPLES = 10          # below this, don't use the model — use raw thresholds

    def __init__(self):
        self.model:   "linear_model.LogisticRegression | None" = None
        self.n_seen:  int  = 0
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if MODEL_FILE.exists():
            try:
                with open(MODEL_FILE, "rb") as f:
                    state = pickle.load(f)
                self.model  = state["model"]
                self.n_seen = state.get("n_seen", 0)
                logging.info("PreferenceEngine loaded — %d decisions seen", self.n_seen)
                return
            except Exception as e:
                logging.warning("PreferenceEngine load failed (%s) — fresh start", e)
        self._init_model()

    def _init_model(self):
        if not RIVER_OK:
            logging.warning("River not available — preference engine disabled")
            return
        self.model  = linear_model.LogisticRegression(optimizer=optim.SGD(lr=0.05))
        self.n_seen = 0

    def save(self):
        if not self.model:
            return
        try:
            with open(MODEL_FILE, "wb") as f:
                pickle.dump({"model": self.model, "n_seen": self.n_seen}, f)
        except Exception as e:
            logging.warning("PreferenceEngine save failed: %s", e)

    # ── learn from a decision ────────────────────────────────────────────────

    def learn(self, proposal: dict, approved: bool, note: str = ""):
        """
        Called immediately when user approves (approved=True) or rejects (False).
        Updates the model in-place — no retraining needed.
        Also appends to the JSONL preference log for transparency and replay.
        """
        if not self.model or not RIVER_OK:
            return

        feats = _featurize(proposal)
        label = 1 if approved else 0
        self.model.learn_one(feats, label)
        self.n_seen += 1

        # append to transparent log (human-readable, replayable)
        entry = {
            "n":          self.n_seen,
            "approved":   approved,
            "note":       note,
            "proposal":   {
                "proposed_name": proposal.get("proposed_name"),
                "domain_code":   proposal.get("domain_code"),
                "ct_code":       proposal.get("ct_code"),
                "status_code":   proposal.get("status_code"),
                "tags":          proposal.get("tags"),
            },
        }
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.debug("pref log write failed: %s", e)

        # auto-save every 50 decisions
        if self.n_seen % 50 == 0:
            self.save()

    # ── predict ──────────────────────────────────────────────────────────────

    def predict(self, proposal: dict) -> float:
        """
        Return probability 0.0–1.0 that this proposal will be approved.
        Returns 0.5 (neutral) if not enough data yet.
        """
        if not self.model or not RIVER_OK or self.n_seen < self.MIN_SAMPLES:
            return 0.5  # neutral — use raw confidence thresholds instead
        try:
            feats = _featurize(proposal)
            proba = self.model.predict_proba_one(feats)
            return proba.get(1, 0.5)
        except Exception:
            return 0.5

    def should_auto_approve(self, proposal: dict, raw_confidence: float,
                            base_threshold: float = 0.72) -> tuple[bool, str]:
        """
        Combine raw classifier confidence with learned preference probability.
        Returns (auto_approve: bool, reason: str).
        """
        pref = self.predict(proposal)

        if self.n_seen < self.MIN_SAMPLES:
            # not enough data — use raw confidence only
            ok     = raw_confidence >= base_threshold
            reason = f"conf={raw_confidence:.2f} (no pref data yet, n={self.n_seen})"
            return ok, reason

        # weighted blend: 60% raw confidence, 40% learned preference
        combined = 0.6 * raw_confidence + 0.4 * pref

        # also: if user has rejected this exact pattern > 2x, force to queue
        if pref < 0.25:
            return False, f"pref={pref:.2f} — pattern repeatedly rejected"

        ok     = combined >= base_threshold
        reason = f"conf={raw_confidence:.2f} pref={pref:.2f} combined={combined:.2f}"
        return ok, reason

    # ── replay ───────────────────────────────────────────────────────────────

    def replay_log(self):
        """Re-train from scratch using the JSONL log. Call after editing the log."""
        if not LOG_FILE.exists():
            return
        self._init_model()
        with open(LOG_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    self.learn(entry["proposal"], entry["approved"])
                except Exception:
                    pass
        self.save()
        logging.info("PreferenceEngine replayed %d entries", self.n_seen)

    def stats(self) -> dict:
        return {
            "n_seen":       self.n_seen,
            "model_ready":  self.n_seen >= self.MIN_SAMPLES,
            "river_ok":     RIVER_OK,
            "log_file":     str(LOG_FILE),
            "model_file":   str(MODEL_FILE),
        }


# ---------------------------------------------------------------------------
# Module-level singleton (shared by fis_namer + approval queue API)
# ---------------------------------------------------------------------------

_engine: PreferenceEngine | None = None

def get_engine() -> PreferenceEngine:
    global _engine
    if _engine is None:
        _engine = PreferenceEngine()
    return _engine


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    e = get_engine()
    print("Stats:", e.stats())
