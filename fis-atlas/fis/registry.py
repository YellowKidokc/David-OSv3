"""FIS registry — the chained dictionary that gives statements their meaning.

The registry is not mutable background infrastructure: every release is an
immutable, versioned, hash-chained object. Events bind to the exact registry
version used to interpret them. Nothing enters execution unless the chain
verifies. Statements (statement.py) are readable; capsules (history.py) are
fingerprints; this module is the dictionary + the chain + the invariants.

    R_v = HASH( "FIS-REGISTRY-v2" || R_{v-1} || Canonical(Registry_v) )
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

try:
    import yaml
except Exception:                       # pragma: no cover
    yaml = None

DEFAULT_REGISTRY = Path(__file__).parent.parent / "fis-registry" / "registry.yaml"
REGISTRY_PREFIX = b"FIS-REGISTRY-v2"


class RegistryError(ValueError):
    pass


class RegistryIntegrityError(RegistryError):
    pass


def _is_hex(s: str) -> bool:
    try:
        bytes.fromhex(s); return True
    except (ValueError, TypeError):
        return False


class Registry:
    def __init__(self, path: str | Path = DEFAULT_REGISTRY):
        self.path = Path(path)
        if yaml is None:
            raise RegistryError("PyYAML required to read the registry (pip install pyyaml)")
        self.data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.version = self.data.get("registry_version", "FIS-LEXICON-?")

    # ---- identity + chain ----
    @property
    def registry_id(self) -> str:
        return (self.data.get("registry") or {}).get("registry_id", "FISREG-????")

    def registry_hash(self) -> str:
        """R_v — binds every event to this exact registry version."""
        chain = dict(self.data.get("registry") or {})
        prev = chain.get("previous_hash") or ""
        content = {k: v for k, v in self.data.items() if k != "registry"}
        chain_meta = {k: v for k, v in chain.items() if k != "content_hash"}
        canon = json.dumps({"content": content, "chain": chain_meta},
                           sort_keys=True, default=str).encode()
        material = REGISTRY_PREFIX + (bytes.fromhex(prev) if _is_hex(prev) else prev.encode()) + canon
        return hashlib.blake2b(material, digest_size=32).hexdigest()

    def verify_chain(self) -> bool:
        declared = (self.data.get("registry") or {}).get("content_hash")
        if declared and declared not in (None, "null"):
            return declared == self.registry_hash()
        return True                     # unsealed registry is allowed pre-seal

    def seal(self) -> str:
        h = self.registry_hash()
        self.data.setdefault("registry", {})["content_hash"] = h
        return h

    def require_verified(self):
        if not self.verify_chain():
            raise RegistryIntegrityError("Registry verification failed; execution blocked.")

    # ---- lookups ----
    def lookup(self, kind: str, code: str) -> str:
        table = self.data.get(kind, {})
        bare = code.lstrip("0") or "0"
        for c in (code, bare, bare.zfill(2), bare.zfill(3)):
            if c in table:
                code = c
                break
        if code not in table:
            raise RegistryError(f"unknown {kind} code: {code!r}")
        if self._superseded(code):
            raise RegistryError(f"code {code} superseded by "
                                f"{self.data['superseded'][code]['replaced_by']}")
        val = table[code]
        return val["name"] if isinstance(val, dict) and "name" in val else val

    def root_set(self, code: str) -> dict:
        rs = (self.data.get("root_sets") or {}).get(code)
        if rs is None:
            raise RegistryError(f"unknown root_set: {code}")
        if not rs.get("manifest_hash"):
            raise RegistryError(f"root_set {code} has no manifest_hash (RULE: hash every manifest)")
        return rs

    def object_set(self, code: str) -> dict:
        os_ = (self.data.get("object_sets") or {}).get(code)
        if os_ is None:
            raise RegistryError(f"unknown object_set: {code}")
        return os_

    def decision(self, code: str) -> dict:
        d = (self.data.get("decisions") or {}).get(code)
        if d is None:
            raise RegistryError(f"unknown decision: {code}")
        return d

    def _superseded(self, code: str) -> bool:
        return code in (self.data.get("superseded") or {})

    # ---- invariants ----
    def add_code(self, kind: str, code: str, value):
        table = self.data.setdefault(kind, {})
        if code in table and table[code] != value:
            raise RegistryError(f"RULE: code {code} already means {table[code]!r}; never reuse")
        table[code] = value

    def supersede(self, code: str, replaced_by: str):
        self.data.setdefault("superseded", {})[code] = {"status": "superseded",
                                                         "replaced_by": replaced_by}

    def supersede_decision(self, old: str, new_id: str, new_ruling: dict, reason: str):
        """Decisions are immutable citations: never edit D14, add D21 that supersedes it."""
        if new_id in (self.data.get("decisions") or {}):
            raise RegistryError(f"decision {new_id} already exists (immutable)")
        self.data.setdefault("decisions", {})[new_id] = {
            "supersedes": old, "reason": reason, "ruling": new_ruling}

    @staticmethod
    def hash_manifest(manifest_path: str | Path) -> str:
        return hashlib.blake2b(Path(manifest_path).read_bytes(), digest_size=32).hexdigest()

    # ---- compiled index ----
    def compile_sqlite(self, db_path: str | Path):
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS registry_entries"
                     "(kind TEXT, code TEXT, value TEXT, PRIMARY KEY(kind,code))")
        for kind in ("operations", "roots", "paths", "strategies", "policies",
                     "results", "periods", "workflows"):
            for code, val in (self.data.get(kind) or {}).items():
                conn.execute("INSERT OR REPLACE INTO registry_entries VALUES(?,?,?)",
                             (kind, str(code), json.dumps(val)))
        conn.execute("INSERT OR REPLACE INTO registry_entries VALUES('meta','registry_hash',?)",
                     (json.dumps(self.registry_hash()),))
        conn.commit(); conn.close()


def load(path: str | Path = DEFAULT_REGISTRY) -> Registry:
    return Registry(path)
