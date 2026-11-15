"""
base.py — the interface every preference engine implements.

Keep it tiny so a new engine is one small file:
  predict(proposal) -> float in [0,1]   (0.5 = neutral / not enough data)
  learn(proposal, approved)             (update from one human decision)
  save() / load() / stats()
  ready                                 (has it seen enough to be trusted?)
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class PreferenceEngine(ABC):
    name: str = "base"
    MIN_SAMPLES: int = 10

    def __init__(self):
        self.n_seen: int = 0

    @property
    def ready(self) -> bool:
        return self.n_seen >= self.MIN_SAMPLES

    @property
    def available(self) -> bool:
        """False if a required library is missing — ensemble skips it."""
        return True

    @abstractmethod
    def predict(self, proposal: dict) -> float:
        ...

    @abstractmethod
    def learn(self, proposal: dict, approved: bool) -> None:
        ...

    def save(self) -> None:
        pass

    def load(self) -> None:
        pass

    def stats(self) -> dict:
        return {"name": self.name, "n_seen": self.n_seen,
                "ready": self.ready, "available": self.available}
