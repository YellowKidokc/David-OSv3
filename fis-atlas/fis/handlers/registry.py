"""Handler registry — call any primitive by 'op/name'.

The shelf is the vocabulary of the system. Workflows compose these; nothing
reimplements them. Mutating handlers (act/*) are the only ones that touch disk,
and none exist yet by design.
"""
from __future__ import annotations

from . import dec_normalize, lok_search, dec_cut, dec_breakdown, sim_dedupe

_SHELF = {
    "dec/normalize_name": dec_normalize.propose,
    "lok/search": lok_search.search,
    "dec/cut": dec_cut.cut,
    "dec/breakdown": dec_breakdown.breakdown,
    "sim/dedupe": sim_dedupe.dedupe,
}


def get(handler_id: str):
    return _SHELF.get(handler_id)


def available() -> list[str]:
    return sorted(_SHELF)
