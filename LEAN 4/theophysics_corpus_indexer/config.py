"""Configuration for the Theophysics corpus indexer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Postgres target database
DB_CONFIG = {
    "host": "192.168.1.177",
    "port": 2665,
    "dbname": "theophysics_corpus",
    "user": "Yellowkid",
    "password": "Moss9pep28$",
}

# Six source roots listed in the build spec
SOURCE_ROOTS: list[str] = [
    "//192.168.2.50/h_hp/Desktop 2/LEAN 4",
    "//192.168.2.50/h_hp/Desktop/___Pipeline_Done_New/One page paper API/LEAN4",
    "//192.168.2.50/h_hp/Desktop/___Pipeline_Done_New/One page paper API/EVIDENCE/OUTBOX",
    "//192.168.2.50/h_hp/Desktop/_____pipeline-workflows-main/LEAN_FLOOR",
    "D:/TEMP_LEAN_ZIP",
    "C:/Users/David/Documents/faiththruphysics.com/04_MASTER_EQUATION",
]

SKIP_DIRS: set[str] = {".lake", ".git", ".venv", "__pycache__", "node_modules", "_support"}
INDEX_EXTS: set[str] = {".lean", ".md", ".txt", ".tex", ".py", ".csv", ".json"}

# Existing record files to ingest, not recompute
MANIFEST_CSV = "//192.168.2.50/h_hp/Desktop 2/LEAN 4/_CANON_SORTED_2026-09-17/00_MANIFEST.csv"
REGISTRY_JSON = "//192.168.2.50/h_hp/Desktop 2/LEAN 4/AXIOM_OUTPUT/_support/registry.json"
MASTER_LIST_CSV = "//192.168.2.50/h_hp/Desktop 2/LEAN 4/AXIOM_OUTPUT/MASTER_LIST.csv"
BATCH_RUNS_DIR = "//192.168.2.50/h_hp/Desktop/_____pipeline-workflows-main/LEAN_FLOOR/03_VERIFIED_RECEIPTS/BATCH_RUNS"

# Series taxonomy
SERIES_LABELS: list[str] = [
    "MASTER_EQUATION",
    "AXIOMS",
    "SPIRITUAL_TERMS",
    "TEN_LAWS",
    "TRINITY",
    "GRACE_COHERENCE",
    "FALL_ENTROPY",
    "GENESIS_QUANTUM",
    "HARNESS_TESTS",
    "LIBRARY",
]

# v1 classification rules — ordered list of (series, regex_pattern).
# These patterns are matched against declaration names / import names for .lean,
# and against file content for non-lean. LIBRARY is handled separately because
# it is allowed to inspect imports and path segments.
CLASS_RULES: list[tuple[str, str]] = [
    ("TRINITY", r"\b(trinity|triune|perichor)\b"),
    ("MASTER_EQUATION", r"\b(chi|listProd|MasterState|CoherenceAlgebra|CoherenceOperator|LawIso|LawModel)\b"),
    ("GRACE_COHERENCE", r"\b(grace|coherence|repair|restor|lindblad)\b"),
    ("FALL_ENTROPY", r"\b(fall|entropy|fracture|decay|sin_)\b"),
    ("TEN_LAWS", r"\b(law[0-9]|tenlaw|weak_force|strong_force|electromag|thermodynam)\b"),
    ("SPIRITUAL_TERMS", r"\b(fruit|agape|joy_|peace_|patience|kindness|justice|mercy|faith_)\b"),
    ("AXIOMS", r"\b(axiom|jenga|divine_order|god_is|primitive)\b"),
    ("HARNESS_TESTS", r"\b(test_|harness|adversarial|counterexample|control_)\b"),
]

# Markers that identify Mathlib / toolchain material
LIBRARY_DECL_MARKERS: set[str] = {
    "RiemannZeta", "TopologicalSpace", "Finsupp", "Etale", "EssSup",
    "RefinedDiscrTree", "Hilbert90", "DefEqTransformations",
}

# A deterministic hash of this config, used in run receipts
CONFIG_HASH = hashlib.sha256(
    json.dumps(
        {
            "source_roots": sorted(SOURCE_ROOTS),
            "skip_dirs": sorted(SKIP_DIRS),
            "index_exts": sorted(INDEX_EXTS),
            "series": SERIES_LABELS,
            "rules": CLASS_RULES,
            "library_markers": sorted(LIBRARY_DECL_MARKERS),
        },
        sort_keys=True,
    ).encode()
).hexdigest()


def project_dir() -> Path:
    return Path(__file__).resolve().parent
