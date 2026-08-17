"""
markov_engine.py — Markov-chain preference predictor.

Treats each naming proposal as a token sequence:
    <S> -> dom_TH -> ct_COD -> tag_CHI -> tag_COH -> st_AC -> <E>
and learns TWO first-order Markov chains — one over APPROVED sequences, one over
REJECTED ones. P(approve) = sigmoid( logP(seq | approved-chain) + log prior
                                     - logP(seq | rejected-chain) - log prior ).

This is a real generative sequence classifier (a different family from the
linear/tree engines), so it adds signal to the ensemble and is a fair contestant
in `compare`. Add-k smoothing keeps unseen transitions finite.
"""
from __future__ import annotations

import json
import math

import config
from .base import PreferenceEngine

_FILE = config.DB_DIR / "pref_markov.json"
_K = 0.5     # add-k smoothing


def _sequence(proposal: dict) -> list:
    toks = [f"dom_{proposal.get('domain_code', 'GN')}",
            f"ct_{proposal.get('ct_code', 'DOC')}"]
    toks += [f"tag_{t}" for t in (proposal.get("tags") or [])]
    toks += [f"st_{proposal.get('status_code', 'AC')}"]
    return ["<S>"] + toks + ["<E>"]


class MarkovEngine(PreferenceEngine):
    name = "markov"
    MIN_SAMPLES = 10

    def __init__(self):
        super().__init__()
        # class -> {state -> {next: count}} and class -> {state -> total}
        self.trans = {0: {}, 1: {}}
        self.totals = {0: {}, 1: {}}
        self.cls = {0: 0, 1: 0}        # class document counts (priors)
        self.vocab = set()
        self.load()

    def _loglik(self, seq, c) -> float:
        V = max(1, len(self.vocab))
        t, tot = self.trans[c], self.totals[c]
        ll = 0.0
        for a, b in zip(seq, seq[1:]):
            num = t.get(a, {}).get(b, 0) + _K
            den = tot.get(a, 0) + _K * V
            ll += math.log(num / den)
        return ll

    def predict(self, proposal: dict) -> float:
        n = self.cls[0] + self.cls[1]
        if not self.ready or n == 0:
            return 0.5
        seq = _sequence(proposal)
        la = self._loglik(seq, 1) + math.log((self.cls[1] + 1) / (n + 2))
        lr = self._loglik(seq, 0) + math.log((self.cls[0] + 1) / (n + 2))
        d = la - lr
        d = max(-30.0, min(30.0, d))
        return round(1.0 / (1.0 + math.exp(-d)), 4)

    def learn(self, proposal: dict, approved: bool) -> None:
        c = 1 if approved else 0
        seq = _sequence(proposal)
        for a, b in zip(seq, seq[1:]):
            self.vocab.add(a); self.vocab.add(b)
            self.trans[c].setdefault(a, {})
            self.trans[c][a][b] = self.trans[c][a].get(b, 0) + 1
            self.totals[c][a] = self.totals[c].get(a, 0) + 1
        self.cls[c] += 1
        self.n_seen += 1

    def save(self) -> None:
        try:
            _FILE.write_text(json.dumps({
                "trans": {str(c): self.trans[c] for c in (0, 1)},
                "totals": {str(c): self.totals[c] for c in (0, 1)},
                "cls": {str(c): self.cls[c] for c in (0, 1)},
                "vocab": sorted(self.vocab),
                "n_seen": self.n_seen,
            }), encoding="utf-8")
        except Exception:
            pass

    def load(self) -> None:
        if not _FILE.exists():
            return
        try:
            s = json.loads(_FILE.read_text(encoding="utf-8"))
            self.trans = {int(c): v for c, v in s.get("trans", {}).items()} or {0: {}, 1: {}}
            self.totals = {int(c): v for c, v in s.get("totals", {}).items()} or {0: {}, 1: {}}
            self.cls = {int(c): v for c, v in s.get("cls", {}).items()} or {0: 0, 1: 0}
            self.vocab = set(s.get("vocab", []))
            self.n_seen = s.get("n_seen", 0)
            for d in (self.trans, self.totals, self.cls):
                d.setdefault(0, {} if d is not self.cls else 0)
                d.setdefault(1, {} if d is not self.cls else 0)
        except Exception:
            self.trans, self.totals, self.cls = {0: {}, 1: {}}, {0: {}, 1: {}}, {0: 0, 1: 0}
