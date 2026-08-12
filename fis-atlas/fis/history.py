"""FIS History Capsule — the tamper-evident fingerprint of the chained history.

    C_n = Trunc_120( HASH( "FIS-HISTORY-v2" || C_{n-1} || R_v || E_n || M_n ) )

Not reversible. It proves which exact history, registry version, manifests, and
preceding capsule produced the current state. The short form (24-char Crockford
Base32 = 120 bits) is for citation; verification uses the full 256-bit digest.

Hash: BLAKE3 if the optional package is present, else stdlib BLAKE2b. The chain
construction is identical either way.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"      # no I L O U
HISTORY_PREFIX = b"FIS-HISTORY-v2"


def _digest(data: bytes, size: int = 32) -> bytes:
    try:
        import blake3                                # optional; matches spec
        return blake3.blake3(data).digest(length=size)
    except Exception:
        return hashlib.blake2b(data, digest_size=size).digest()


def crockford32(data: bytes, chars: int = 24) -> str:
    """First 120 bits (15 bytes) -> 24 Crockford Base32 chars."""
    bits = int.from_bytes(data[:15], "big")
    return "".join(CROCKFORD[(bits >> (5 * (chars - 1 - i))) & 31] for i in range(chars))


@dataclass
class Capsule:
    short: str            # 24-char display / citation
    full: str             # blake2b/blake3 hex (256-bit) for verification
    previous_full: str    # C_{n-1}


def next_capsule(previous_full: str, registry_hash: str, event_bytes: bytes,
                 manifest_hashes: list[str]) -> Capsule:
    material = (HISTORY_PREFIX
                + bytes.fromhex(previous_full) if previous_full else HISTORY_PREFIX)
    material += bytes.fromhex(registry_hash) if registry_hash else b""
    material += event_bytes
    for m in sorted(manifest_hashes):
        material += bytes.fromhex(m) if _is_hex(m) else m.encode()
    full = _digest(material, 32)
    return Capsule(short="H:" + crockford32(full), full=full.hex(),
                   previous_full=previous_full)


def verify(capsule: Capsule, registry_hash: str, event_bytes: bytes,
           manifest_hashes: list[str]) -> bool:
    recomputed = next_capsule(capsule.previous_full, registry_hash, event_bytes, manifest_hashes)
    return recomputed.full == capsule.full and recomputed.short == capsule.short


def _is_hex(s: str) -> bool:
    try:
        bytes.fromhex(s)
        return True
    except ValueError:
        return False
