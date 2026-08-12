"""FIS operational language — the shared codebook.

Loads the YAML registry (readable source of truth), compiles a SQLite index,
encodes/decodes the fixed 24-char capsule, and decompresses any code to plain
English. Enforces the non-negotiable rules: never reuse a code, supersede rather
than overwrite, hash every manifest, every code decompressible.

Capsule layout (24 chars, fixed positions):
    1      schema version
    2-5    node / collection id
    6-9    set / manifest id
    10     operation
    11-12  source-root code
    13-14  destination-root code
    15-17  policy code
    18-19  time-window code
    20-21  result code
    22-24  integrity check (derived)
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

FIELDS = [("version", 1, 1), ("node", 2, 5), ("manifest", 6, 9), ("operation", 10, 10),
          ("source", 11, 12), ("destination", 13, 14), ("policy", 15, 17),
          ("period", 18, 19), ("result", 20, 21), ("checksum", 22, 24)]
KIND_TABLE = {"operation": "operations", "source": "roots", "destination": "roots",
              "policy": "policies", "period": "periods", "result": "results"}


class RegistryError(ValueError):
    pass


class Registry:
    def __init__(self, path: str | Path = DEFAULT_REGISTRY):
        self.path = Path(path)
        if yaml is None:
            raise RegistryError("PyYAML required to read the registry (pip install pyyaml)")
        self.data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.version = self.data.get("registry_version", "FIS-LEXICON-?")

    # ---- lookups ----
    def lookup(self, kind: str, code: str) -> str:
        table = self.data.get(kind, {})
        # tolerate zero-padding differences (003 <-> 03 <-> 3)
        bare = code.lstrip("0") or "0"
        for c in (code, bare, bare.zfill(2), bare.zfill(3)):
            if c in table:
                code = c
                break
        if code not in table:
            raise RegistryError(f"unknown {kind} code: {code!r}")
        if self._superseded(code):
            raise RegistryError(f"code {code} is superseded by {self.data['superseded'][code]['replaced_by']}")
        val = table[code]
        return val["name"] if isinstance(val, dict) and "name" in val else val

    def _superseded(self, code: str) -> bool:
        return code in (self.data.get("superseded") or {})

    # ---- registry rules ----
    def add_code(self, kind: str, code: str, value):
        table = self.data.setdefault(kind, {})
        if code in table and table[code] != value:
            raise RegistryError(f"RULE: code {code} already means {table[code]!r}; never reuse")
        table[code] = value

    def supersede(self, code: str, replaced_by: str):
        self.data.setdefault("superseded", {})[code] = {"status": "superseded",
                                                         "replaced_by": replaced_by}

    def hash_manifest(self, manifest_path: str | Path) -> str:
        h = hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()
        return h

    # ---- capsule ----
    def encode_capsule(self, node: str, manifest: str, operation: str, source: str,
                       destination: str, policy: str, period: str, result: str) -> str:
        body = (f"{self._vchar()}{node:0>4.4}{manifest:0>4.4}{operation:.1}"
                f"{source:0>2.2}{destination:0>2.2}{policy:0>3.3}{period:0>2.2}{result:0>2.2}")
        return body + self._checksum(body)

    def _vchar(self) -> str:
        # "FIS-LEXICON-2" -> "2"
        return self.version.rsplit("-", 1)[-1][:1] or "1"

    @staticmethod
    def _checksum(body: str) -> str:
        return hashlib.sha256(body.encode()).hexdigest()[:3].upper()

    def decode_capsule(self, capsule: str) -> dict:
        if len(capsule) != 24:
            raise RegistryError(f"capsule must be 24 chars, got {len(capsule)}")
        body, check = capsule[:21], capsule[21:]
        if self._checksum(body) != check:
            raise RegistryError("capsule integrity check failed")
        out = {}
        for name, a, b in FIELDS:
            out[name] = capsule[a - 1:b].strip("0") if name in ("source", "destination") else capsule[a - 1:b]
        return out

    def decompress(self, capsule: str) -> str:
        d = self.decode_capsule(capsule)
        def safe(kind, code):
            try:
                return self.lookup(kind, code)
            except RegistryError:
                return f"?{code}"
        parts = [
            f"schema {d['version']}",
            f"operation {safe('operations', d['operation'])}",
            f"from {safe('roots', d['source'])}",
            f"to {safe('roots', d['destination'])}",
            f"policy {safe('policies', d['policy'])}",
            f"result {safe('results', d['result'])}",
        ]
        return " · ".join(parts)


def folder_capsule(reg: "Registry", object_id: str, risk: str) -> str:
    """A decompressible capsule stamped at the bottom of a folder's .fisnote."""
    node = (object_id or "N000").replace("-", "")[-4:].upper().ljust(4, "0")
    policy = "06" if risk == "red" else "01"           # protected vs observe-only
    period = next(iter(reg.data.get("periods", {})), "T0")
    return reg.encode_capsule(node=node, manifest="0000", operation="L",
                              source="00", destination="00", policy=policy,
                              period=period, result="00")

    # ---- SQLite compiled index ----
    def compile_sqlite(self, db_path: str | Path):
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE IF NOT EXISTS registry_entries(kind TEXT, code TEXT, value TEXT, PRIMARY KEY(kind,code))")
        for kind in ("operations", "roots", "paths", "strategies", "policies", "results", "periods"):
            for code, val in (self.data.get(kind) or {}).items():
                conn.execute("INSERT OR REPLACE INTO registry_entries VALUES(?,?,?)",
                             (kind, str(code), json.dumps(val)))
        conn.commit(); conn.close()


def load(path: str | Path = DEFAULT_REGISTRY) -> Registry:
    return Registry(path)
