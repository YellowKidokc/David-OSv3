"""Provider extension contract. No provider loads or network calls by default."""
from typing import Protocol


class SuggestionProvider(Protocol):
    def suggest(self, evidence: dict) -> dict: ...


class OfflineProvider:
    def suggest(self, evidence):
        return {'suggestions': [], 'why': 'AI assistance is disabled'}
