"""Handler registry — call a handler by 'op/name'. Never executes fs mutations
here; dec handlers PROPOSE, act handlers (later) are the only ones that touch disk.
"""
from __future__ import annotations

from . import dec_normalize

_SHELF = {
    "dec/normalize_name": dec_normalize.propose,
}


def get(handler_id: str):
    return _SHELF.get(handler_id)


def available() -> list[str]:
    return sorted(_SHELF)
