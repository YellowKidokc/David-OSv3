"""The op-code vocabulary — the shared alphabet every file/handler speaks.

Three letters, one per pipeline stage. A file's category travels with it via a
`# fis-op: <code>` tag (scripts) or a filename infix `name.<code>.md` (notes).
"""
from __future__ import annotations

OP_CODES = {
    "lok": "Look / scan (read-only inventory)",
    "idn": "Identity (hash / structural fingerprint)",
    "und": "Understand (classify / tag)",
    "sim": "Similarity (near-dup / folder compare)",
    "dec": "Decide (propose rename / move — never executes)",
    "act": "Act (execute approved actions — the only mutating stage)",
    "gov": "Govern (canon / report / audit ledger)",
    "lrn": "Learn (preference / prediction)",
    "aut": "Automate (watch / daemon / schedule)",
}

# Which stages are allowed to touch the filesystem. Only 'act'.
MUTATING = {"act"}


def describe(code: str) -> str:
    return OP_CODES.get(code, f"unknown op-code: {code}")


def is_mutating(code: str) -> bool:
    return code in MUTATING
