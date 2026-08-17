"""
config.py — paths, constants, data model, and YAML config loading.

Single source of truth for the whole pipeline. Editable YAML lives in config/;
if a YAML file or pyyaml is missing we fall back to the inline defaults here, so
the system always runs.

HARD RULE: this is a READ-ONLY, PROPOSE-ONLY system. It scans -> fingerprints ->
classifies -> proposes names -> logs everything to SQLite + JSONL. It NEVER
renames, moves, or deletes the user's files. Applying is a separate, later worker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any
import json

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_DIR = Path(__file__).resolve().parent.parent      # ...\theophysics-fis
CONFIG_DIR  = PROJECT_DIR / "config"
SYSTEM_DIR  = PROJECT_DIR / "system"
DB_DIR      = SYSTEM_DIR / "db"
LEDGER_DIR  = SYSTEM_DIR / "ledger"
PLANS_DIR   = SYSTEM_DIR / "rename_plans"
REPORTS_DIR = SYSTEM_DIR / "reports"
TEXT_DIR    = SYSTEM_DIR / "extracted_text"

for _d in (DB_DIR, LEDGER_DIR, PLANS_DIR, REPORTS_DIR, TEXT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Spine DB — system of record for THIS pipeline (clean schema).
DB_PATH = DB_DIR / "filebrain.sqlite"

# Reference corpus — the real 819k-row catalog (read-only enrichment lookups).
# fis_catalog.db is 0 bytes (never ran); do NOT use it.
REFERENCE_DB_PATH = r"D:\DONT TOUCH BOOT UP\filetagger\chi_catalog_v2.db"

# Optional lexicon workbook for the chi engine.
LEXICON_PATH = r"D:\DONT TOUCH BOOT UP\theophysics_cross_domain_lexicon.xlsx"

# Ledger files (JSONL, append-only).
EVENTS_LOG  = LEDGER_DIR / "file_events.jsonl"
RENAME_LOG  = LEDGER_DIR / "rename_actions.jsonl"
ERRORS_LOG  = LEDGER_DIR / "errors.jsonl"


# --------------------------------------------------------------------------- #
# YAML loading (optional dependency, inline fallback)
# --------------------------------------------------------------------------- #
def _load_yaml(name: str, fallback: dict) -> dict:
    path = CONFIG_DIR / name
    try:
        import yaml  # optional
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else fallback
    except Exception:
        pass
    return fallback


# --------------------------------------------------------------------------- #
# Code tables (mirrors config/naming_rules.yaml; see FIS_NAMING_SPEC.md)
# --------------------------------------------------------------------------- #
_NAMING_FALLBACK = {
    "separator": "__",
    "tag_separator": "-",
    "max_tags": 3,
    "date_format": "%Y%m%d",
    "max_filename_length": 180,
    "auto_approve_threshold": 0.72,
    "queue_threshold": 0.45,
}
NAMING = _load_yaml("naming_rules.yaml", _NAMING_FALLBACK)

# 2-letter DOMAIN codes -> human label
DOMAIN_LABELS: Dict[str, str] = {
    "TH": "Theophysics / Theology", "DT": "Day Trading / Data", "CD": "Code / Dev",
    "PH": "Physics", "CS": "Consciousness", "EP": "Epistemology", "MT": "Metaphysics",
    "MR": "Morality", "IF": "Information", "LG": "Legal / Law", "KG": "Knowledge Graph",
    "EV": "Evidence / Research", "AI": "Artificial Intelligence", "TR": "Trading",
    "MD": "Media", "GN": "General",
}

CONTENT_TYPES: List[str] = [
    "document", "code", "data", "note", "config", "paper", "image", "video",
    "audio", "binary",
]
STATUS_VALUES: List[str] = ["draft", "active", "final", "archive", "review"]

# Extension -> content_type fallback
EXT_CONTENT_TYPE: Dict[str, str] = {
    ".md": "document", ".txt": "note", ".pdf": "document", ".doc": "document",
    ".docx": "document", ".html": "document", ".htm": "document", ".rtf": "document",
    ".py": "code", ".js": "code", ".ts": "code", ".ahk": "code", ".sh": "code",
    ".ps1": "code", ".bat": "code", ".java": "code", ".c": "code", ".cpp": "code",
    ".csv": "data", ".json": "data", ".xlsx": "data", ".xls": "data", ".db": "data",
    ".sqlite": "data", ".parquet": "data", ".yaml": "config", ".yml": "config",
    ".toml": "config", ".ini": "config", ".cfg": "config",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".webp": "image", ".svg": "image", ".bmp": "image", ".tiff": "image",
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".avi": "video",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".m4a": "audio",
}

# Folder symptom registry (folder_symptom_registry.xlsx). Detectors live in
# inventory_scan.detect_folder_symptoms().
SYMPTOM_REGISTRY: List[Dict[str, str]] = [
    {"id": "S01", "cat": "Structural", "name": "Extension swamp",     "sev": "medium"},
    {"id": "S02", "cat": "Structural", "name": "Version sprawl",      "sev": "medium"},
    {"id": "S03", "cat": "Structural", "name": "Depth explosion",     "sev": "low"},
    {"id": "S04", "cat": "Structural", "name": "Flat overload",       "sev": "medium"},
    {"id": "S05", "cat": "Structural", "name": "Orphan sidecar",      "sev": "low"},
    {"id": "S06", "cat": "Structural", "name": "Naming collision",    "sev": "high"},
    {"id": "S07", "cat": "Structural", "name": "Project scatter",     "sev": "high"},
    {"id": "S08", "cat": "Structural", "name": "Phantom reference",   "sev": "medium"},
    {"id": "C01", "cat": "Content",    "name": "Duplicate cluster",   "sev": "medium"},
    {"id": "C02", "cat": "Content",    "name": "Format redundancy",   "sev": "low"},
    {"id": "C03", "cat": "Content",    "name": "Draft graveyard",     "sev": "low"},
    {"id": "C04", "cat": "Content",    "name": "Document chaos",      "sev": "medium"},
    {"id": "C05", "cat": "Content",    "name": "Media dump",          "sev": "low"},
    {"id": "C06", "cat": "Content",    "name": "Unknown blobs",       "sev": "medium"},
    {"id": "C07", "cat": "Content",    "name": "Encoding chaos",      "sev": "medium"},
    {"id": "C08", "cat": "Content",    "name": "Incomplete extract",  "sev": "low"},
    {"id": "T01", "cat": "Temporal",   "name": "Time bomb",           "sev": "low"},
    {"id": "T02", "cat": "Temporal",   "name": "Burst dump",          "sev": "medium"},
    {"id": "T03", "cat": "Temporal",   "name": "Stale pipeline",      "sev": "medium"},
    {"id": "T04", "cat": "Temporal",   "name": "Abandoned workspace", "sev": "low"},
]

FILE_ROLES = ["canonical", "fragile", "anomaly", "duplicate", "near_duplicate",
              "orphan", "archive", "unknown"]

# --------------------------------------------------------------------------- #
# Ignore patterns (mirrors config/ignore_patterns.yaml)
# --------------------------------------------------------------------------- #
_IGNORE_FALLBACK = {
    "skip_dirs": [
        ".git", "__pycache__", ".venv", "venv", "node_modules", ".obsidian",
        "System Volume Information", "$Recycle.Bin", ".trash", "salvaged",
    ],
    "skip_names": ["thumbs.db", "desktop.ini", ".ds_store"],
    "skip_exts": [".chi", ".fisnote", ".fmeta"],
}
IGNORE = _load_yaml("ignore_patterns.yaml", _IGNORE_FALLBACK)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class FileRecord:
    """One file as it moves through the pipeline. Modules set fields in place."""
    # identity / fingerprint
    path: str
    name: str
    extension: str
    size_bytes: int
    sha256: str
    modified_at: str = ""
    created_at: str = ""
    source_root: str = ""
    content_preview: str = ""
    fuzzy_hash: str = ""

    # classification (5 tags + chi profile)
    domain: Optional[str] = None              # 2-letter DOMAIN code
    domain_label: Optional[str] = None
    content_type: Optional[str] = None
    status: Optional[str] = None
    date: Optional[str] = None
    topic_slug: Optional[str] = None
    chi_vector: Optional[dict] = None
    chi_primary: Optional[str] = None
    chi_secondary: Optional[str] = None
    chi_confidence: Optional[float] = None
    domain_scores: Optional[dict] = None
    evidence: Optional[float] = None
    fruit: Optional[float] = None
    anti_fruit: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    role: str = "unknown"

    # capability gate (subject category + access tier + processing route)
    gate_category: Optional[str] = None
    gate_tier: Optional[str] = None
    gate_route: Optional[str] = None
    gate_access: Optional[str] = None

    # proposal / review
    proposed_name: Optional[str] = None
    decision: Optional[str] = None            # auto_approve | queue | skip
    reason: Optional[str] = None
    confidence: Optional[float] = None
    approved: Optional[bool] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ScanConfig:
    scan_roots: List[str]
    file_types: List[str] = field(default_factory=lambda: [".md", ".txt", ".html"])
    db_path: str = str(DB_PATH)
    output_dir: str = str(REPORTS_DIR)
    content_preview_chars: int = 4000
    min_file_size: int = 1
    max_file_size: int = 50_000_000
    max_files: int = 0                 # 0 = unlimited
    commit_every: int = 100            # persist + release lock every N files
    write_sidecars: bool = False
    store_db: bool = True
    enrich: bool = True                # run TF-IDF + WordNet enricher on low-confidence files
    reference_db: str = REFERENCE_DB_PATH
    gate: bool = True                  # run capability gate + folder category-Markov smoothing
