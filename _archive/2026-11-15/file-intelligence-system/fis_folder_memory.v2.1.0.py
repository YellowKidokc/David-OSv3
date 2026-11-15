"""Generate compact, linked FIS folder memories from one SQLite registry.

This tool is deliberately inventory-only.  It never moves, renames, deletes,
or promotes content.  ``--write`` is required before it writes a .fisnote and
an existing note is preserved as a timestamped sibling first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import urllib.request
from html import escape
from urllib.parse import quote
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from fis_namer import (
    CT_CODES, DOMAIN_CODES, STATUS_CODES, TAG_ABBREVS, extract_tags,
    propose_lossless_address, propose_name, resolve_domain,
)
from fis_classifier import (CHI_SIGNALS, DOMAIN_SIGNALS, LAW_SIGNALS,
                            classify_file, classify_document_type)


SCHEMA = "folder-memory.v2"
IGNORED_DIRS = {
    ".git", ".fis", ".trash", "#recycle", "$recycle.bin", "system volume information", ".claude", ".obsidian",
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", ".lake", "target", "site-packages", "_internal",
}
FIS_HTML_FILENAME = "FIS.html"
SKIP_FILES = {".fisnote", "fis.html", "fis_folder_index.html", "thumbs.db", "desktop.ini", ".ds_store"}
GENERATED_FILE_NOTE_MARKER = "FIS file-memory.v2: generated sidecar view"
MEQ_VARIABLE_TAGS = {
    "G": ["G", "grace"],
    "M": ["M", "moral alignment"],
    "E": ["E", "truth signal"],
    "S": ["S_eff", "entropy"],
    "T": ["T", "time kairos"],
    "K": ["K", "knowledge logos"],
    "R": ["R", "relational frame"],
    "Q": ["Q", "quantum uncertainty"],
    "F": ["F", "faith fruit"],
    "C": ["C", "christ coherence"],
}
# ─── Master Equation Namer: coupling pairs ────────────────────────────────────
COUPLING_PAIRS = [
    ("G", "C"),  # Grace ↔ Christ/Coherence (L01 ↔ L10)
    ("M", "F"),  # Moral Alignment ↔ Faith/Fruit (L02 ↔ L04)
    ("E", "Q"),  # Truth Signal ↔ Quantum/Uncertainty (L03 ↔ L07)
    ("S", "R"),  # Entropy ↔ Relational Frame (L05 ↔ L08)
    ("T", "K"),  # Time/Kairos ↔ Knowledge/Logos (L08 ↔ L06)
]


def meq_namer_string(chi: dict) -> str:
    """Build the Master Equation Namer identity string from a CHI vector.

    Format: G3 M2 E3 S1 T2 K3 R1 Q2 F3 C3 :: [G.C] [M.F] [E.Q] [S.R] [T.K]
    """
    if not chi or not any(chi.values()):
        return ""
    vector = " ".join(f"{var}{chi.get(var, 0)}" for var in "G M E S T K R Q F C".split())
    pairs = " ".join(f"[{a}.{b}]" for a, b in COUPLING_PAIRS)
    return f"{vector} :: {pairs}"


def meq_namer_short(chi: dict) -> str:
    """Shortened MEQ name: only non-zero variables + active coupling pairs."""
    if not chi or not any(chi.values()):
        return ""
    nonzero = [f"{var}{chi[var]}" for var in "G M E S T K R Q F C".split() if chi.get(var, 0) > 0]
    active_pairs = []
    for a, b in COUPLING_PAIRS:
        if chi.get(a, 0) > 0 or chi.get(b, 0) > 0:
            active_pairs.append(f"[{a}.{b}]")
    return " ".join(nonzero) + (" :: " + " ".join(active_pairs) if active_pairs else "")


PRESENTATION_EXTENSIONS = {".html", ".htm"}
TEXT_KEYWORD_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".html", ".htm", ".json", ".yaml", ".yml", ".tex", ".lean", ".py"}
KEYWORD_STOPWORDS = {
    "about", "after", "and", "are", "article", "case", "chapter", "code", "document", "file",
    "for", "from", "into", "its", "master", "notes", "part", "paper", "project", "section",
    "that", "the", "their", "this", "through", "under", "with", "without", "your",
}


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def digest(value: str, prefix: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8', 'replace')).hexdigest()[:12]}"


def item_id(path: Path, prefix: str) -> str:
    return digest(str(path.resolve()).lower(), prefix)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def relative_link(source_folder: Path, target: Path) -> str:
    try:
        relative = Path(__import__("os").path.relpath(target, source_folder)).as_posix()
        return quote(relative, safe="/-_.")
    except ValueError:
        return target.as_uri()


def markdown_label(value: str) -> str:
    """Keep literal filenames readable without allowing them to break a link."""
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def inferred_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".md", ".txt", ".doc", ".docx", ".pdf", ".html", ".htm"}:
        return "article" if ext in {".md", ".html", ".htm"} else "document"
    if ext in {".py", ".js", ".ts", ".ahk", ".ps1", ".sh", ".bat"}:
        return "script"
    if ext in {".json", ".csv", ".xlsx", ".xls", ".sqlite", ".db"}:
        return "data"
    if ext in {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}:
        return "media"
    if ext in {".zip", ".7z", ".rar", ".tar", ".gz"}:
        return "archive"
    if ext in {".yaml", ".yml", ".toml", ".ini", ".env"}:
        return "config"
    return "other"


def html_features(path: Path) -> dict[str, bool]:
    features = {"has_topbar": False, "has_audio": False, "has_equations": False, "has_claims": False}
    if path.suffix.lower() not in PRESENTATION_EXTENSIONS or path.stat().st_size > 8_000_000:
        return features
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return features
    features["has_topbar"] = "topbar" in text or "top-bar" in text
    features["has_audio"] = "<audio" in text or "audio-data" in text
    features["has_equations"] = "katex" in text or "mathjax" in text or "\\(" in text
    features["has_claims"] = "claim" in text
    return features


def reading_level(path: Path) -> str:
    # An honest placeholder: the NLP rail can replace this when it is healthy.
    return "unscanned"


def directory_kind(path: Path) -> str:
    lower = path.name.lower()
    if any(word in lower for word in ("archive", "backup", "zzz")):
        return "archive"
    if any(word in lower for word in ("code", "script", "api", "app", "python")):
        return "programming"
    if any(word in lower for word in ("paper", "chapter", "canon", "article", "essay")):
        return "document"
    return "mixed"


def folder_name_code(folder: Path, files: list[Path], folder_type: str, status: str = "active") -> dict[str, object]:
    """Use the existing FIS compressed-name grammar as folder metadata.

    It describes the folder but never renames it.  Folder context can establish
    a domain only where the folder name itself is explicit; otherwise the FIS
    resolver retains its generic result.
    """
    context = f"{folder.name} {folder.parent}"
    lower = context.lower()
    declared_meq = any(
        "master_equation" in file.stem.lower() or "master equation" in file.stem.lower()
        for file in files
    )
    chi_domain = "theology" if declared_meq or any(token in lower for token in ("apologetic", "theophysics", "faith through physics")) else ""
    # Explicit folder identity is stronger than incidental words in an ancestor
    # path (for example, "Faith Through Physics" must not make Apologetics PH).
    domain = resolve_domain(chi_domain, folder.name, "" if chi_domain else str(folder))
    content_type = "code" if folder_type == "programming" else "document"
    ct = CT_CODES[content_type]
    tags = extract_tags(folder.name, " ".join(p.stem for p in files), domain)
    source_mtime = max((file.stat().st_mtime for file in files), default=folder.stat().st_ctime)
    date = datetime.fromtimestamp(source_mtime).strftime("%Y%m%d")
    status_code = STATUS_CODES.get(status, "AC")
    code = f"{domain}__{ct}__{'-'.join(tags) if tags else 'GN'}__{date}__{status_code}"
    domain_meaning = next((name for name, value in DOMAIN_CODES.items() if value == domain), "general")
    tag_meanings = {
        code: "/".join(keywords[:2])
        for keywords, code in TAG_ABBREVS if code in tags
    }
    return {"code": code, "domain": domain, "domain_meaning": domain_meaning, "ct": ct,
            "tags": tags, "date": date, "status": status_code, "tag_meanings": tag_meanings}


def folder_lossless_address(folder: Path, files: list[Path]) -> dict[str, object]:
    """Build an address from local evidence only; never call an AI or mutate files."""
    sample_parts: list[str] = []
    supported = {".md", ".txt", ".html", ".htm"}
    for file in files[:20]:
        sample_parts.append(file.stem)
        if file.suffix.lower() not in supported or file.stat().st_size > 2_000_000:
            continue
        try:
            sample_parts.append(file.read_text(encoding="utf-8", errors="ignore")[:8_000])
        except OSError:
            pass
    source_mtime = max((file.stat().st_mtime for file in files), default=folder.stat().st_ctime)
    return propose_lossless_address(folder.name, "\n".join(sample_parts), source_mtime)


def file_lossless_address(path: Path) -> dict[str, object]:
    """Give each stored file a safe internal address without changing the file."""
    sample = path.stem
    if path.suffix.lower() in {".md", ".txt", ".html", ".htm"} and path.stat().st_size <= 2_000_000:
        try:
            sample += "\n" + path.read_text(encoding="utf-8", errors="ignore")[:16_000]
        except OSError:
            pass
    return propose_lossless_address(path.stem, sample, path.stat().st_mtime)


def local_keywords(path: Path, classification: dict[str, object]) -> list[str]:
    """Build searchable, deterministic tags from existing FIS signals and source text.

    This deliberately does not call the classifier's optional AI fallback.  These
    are retrieval hints, not semantic verdicts or canon decisions.
    """
    tags: list[str] = []
    domain = classification.get("domain", {})
    law = classification.get("law", {})
    for value in (
        domain.get("name") if isinstance(domain, dict) else None,
        classification.get("chi_factor"),
        classification.get("chi_name"),
        law.get("name") if isinstance(law, dict) else None,
        classification.get("content_type"),
        classification.get("file_role"),
    ):
        if value and str(value).lower() not in {"none", "unclassified", "document"}:
            tags.append(str(value))
    chi_vector = classification.get("chi", {})
    if isinstance(chi_vector, dict):
        for variable, score in chi_vector.items():
            if int(score or 0) <= 0:
                continue
            tags.extend(MEQ_VARIABLE_TAGS.get(variable, [variable]))

    text = path.stem.replace("_", " ").replace("-", " ").lower()
    if path.suffix.lower() in TEXT_KEYWORD_EXTENSIONS and path.stat().st_size <= 2_000_000:
        try:
            text += "\n" + path.read_text(encoding="utf-8", errors="ignore")[:80_000].lower()
        except OSError:
            pass
    controlled: list[tuple[int, str]] = []
    for terms in (CHI_SIGNALS, DOMAIN_SIGNALS, LAW_SIGNALS):
        values = terms.values()
        for item in values:
            keywords = item.get("keywords", []) if isinstance(item, dict) else item
            for keyword in keywords:
                if len(keyword) > 2 and keyword in text:
                    controlled.append((text.count(keyword), keyword))
    # The filename contributes a few extra, literal retrieval handles without
    # claiming that every ordinary word is a meaningful classification.
    filename_words = re.findall(r"[a-z][a-z0-9]{3,}", path.stem.lower())
    # Rank literal signal matches by recurrence.  This keeps a repeated phrase
    # such as "master equation" ahead of a one-off vocabulary hit.
    tags.extend(keyword for _, keyword in sorted(controlled, key=lambda item: (-item[0], -len(item[1]), item[1]))[:12])
    tags.extend(word for word in filename_words if word not in KEYWORD_STOPWORDS)
    seen: set[str] = set()
    return [tag for tag in tags if not (tag.lower() in seen or seen.add(tag.lower()))][:20]


def direct_files(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir()
        if p.is_file()
        and p.name.lower() not in SKIP_FILES
        and not p.name.lower().endswith(".fisnote")
        and not p.name.startswith(".fisnote.legacy.")
    )


def direct_children(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_dir() and p.name.lower() not in IGNORED_DIRS)


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS folder_memory (
            folder_id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            folder_type TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT 'UNRESOLVED',
            domain TEXT NOT NULL DEFAULT 'unclassified', series_name TEXT,
            chain_steps TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'active',
            owner TEXT NOT NULL DEFAULT 'UNRESOLVED', canonical_source INTEGER NOT NULL DEFAULT 0,
            parent_backbone TEXT, file_count INTEGER NOT NULL, child_folder_count INTEGER NOT NULL,
            created_at TEXT, last_scanned TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
            compressed_name TEXT, compressed_name_detail TEXT NOT NULL DEFAULT '{}',
            lossless_address TEXT, lossless_address_detail TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS file_memory (
            file_id TEXT PRIMARY KEY, folder_id TEXT NOT NULL, path TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, item_type TEXT NOT NULL, format TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT 'unclassified', series_name TEXT,
            chain_steps TEXT NOT NULL DEFAULT '[]', reading_level TEXT NOT NULL,
            has_topbar INTEGER NOT NULL DEFAULT 0, has_audio INTEGER NOT NULL DEFAULT 0,
            has_equations INTEGER NOT NULL DEFAULT 0, has_claims INTEGER NOT NULL DEFAULT 0,
            canonical INTEGER NOT NULL DEFAULT 0, superseded_by TEXT,
            content_fingerprint TEXT, node_count INTEGER, status TEXT NOT NULL DEFAULT 'unclassified',
            last_modified TEXT, size_bytes INTEGER NOT NULL, last_scanned TEXT NOT NULL,
            lossless_address TEXT, lossless_address_detail TEXT NOT NULL DEFAULT '{}',
            local_classification_json TEXT NOT NULL DEFAULT '{}', keywords_json TEXT NOT NULL DEFAULT '[]',
            keywords_text TEXT NOT NULL DEFAULT '',
            ai_enrichment_json TEXT NOT NULL DEFAULT '{}', ai_model TEXT, ai_reviewed_at TEXT,
            ai_source_fingerprint TEXT, proposed_name TEXT, proposed_name_detail TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_file_memory_folder ON file_memory(folder_id);
        CREATE INDEX IF NOT EXISTS idx_file_memory_fingerprint ON file_memory(content_fingerprint);
        """
    )
    for statement in (
        "ALTER TABLE folder_memory ADD COLUMN compressed_name TEXT",
        "ALTER TABLE folder_memory ADD COLUMN compressed_name_detail TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE folder_memory ADD COLUMN lossless_address TEXT",
        "ALTER TABLE folder_memory ADD COLUMN lossless_address_detail TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE file_memory ADD COLUMN lossless_address TEXT",
        "ALTER TABLE file_memory ADD COLUMN lossless_address_detail TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE file_memory ADD COLUMN local_classification_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE file_memory ADD COLUMN keywords_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE file_memory ADD COLUMN keywords_text TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE file_memory ADD COLUMN ai_enrichment_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE file_memory ADD COLUMN ai_model TEXT",
        "ALTER TABLE file_memory ADD COLUMN ai_reviewed_at TEXT",
        "ALTER TABLE file_memory ADD COLUMN ai_source_fingerprint TEXT",
        "ALTER TABLE file_memory ADD COLUMN proposed_name TEXT",
        "ALTER TABLE file_memory ADD COLUMN proposed_name_detail TEXT NOT NULL DEFAULT '{}'",
        # Second classification axis: what TYPE of document this is.
        "ALTER TABLE file_memory ADD COLUMN doc_type TEXT NOT NULL DEFAULT 'UNSCANNED'",
        "ALTER TABLE file_memory ADD COLUMN type_confidence REAL NOT NULL DEFAULT 0.0",
        "ALTER TABLE file_memory ADD COLUMN type_scores_json TEXT NOT NULL DEFAULT '{}'",
        "ALTER TABLE file_memory ADD COLUMN type_evidence_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE file_memory ADD COLUMN doc_type_scanned_at TEXT",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_file_memory_doc_type ON file_memory(doc_type)")
    except sqlite3.OperationalError:
        pass
    ensure_compat_views(conn)
    return conn


def ensure_compat_views(conn: sqlite3.Connection) -> None:
    for name in ("files", "folders"):
        row = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()
        if row and row[0] == "view":
            conn.execute(f"DROP VIEW {name}")
    conn.executescript(
        """
        CREATE VIEW IF NOT EXISTS files AS
            SELECT
                fm.file_id AS file_id,
                fm.path AS path,
                fol.path AS folder_path,
                fm.name AS name,
                fm.lossless_address AS internal_address,
                fm.lossless_address AS lossless_address,
                fm.proposed_name AS proposed_name,
                fm.format AS format,
                fm.item_type AS role,
                fm.domain AS domain,
                fm.keywords_text AS keywords,
                fm.status AS status,
                fm.content_fingerprint AS sha256,
                fm.size_bytes AS size_bytes,
                fm.last_modified AS modified_at,
                fm.last_scanned AS scanned_at,
                NULL AS score
            FROM file_memory fm
            LEFT JOIN folder_memory fol ON fol.folder_id = fm.folder_id;
        CREATE VIEW IF NOT EXISTS folders AS
            SELECT
                folder_id AS folder_id,
                path AS path,
                name AS name,
                compressed_name AS fis_descriptor,
                lossless_address AS lossless_address,
                folder_type AS folder_type,
                domain AS domain,
                file_count AS file_count,
                child_folder_count AS child_count,
                last_scanned AS scanned_at,
                NULL AS score
            FROM folder_memory;
        """
    )


def upsert_folder(conn: sqlite3.Connection, folder: Path, files: list[Path], children: list[Path]) -> str:
    fid = item_id(folder, "FLD")
    created = datetime.fromtimestamp(folder.stat().st_ctime, UTC).replace(microsecond=0).isoformat()
    folder_type = directory_kind(folder)
    name_detail = folder_name_code(folder, files, folder_type)
    lossless_detail = folder_lossless_address(folder, files)
    conn.execute(
        """INSERT INTO folder_memory(folder_id,path,name,folder_type,file_count,child_folder_count,created_at,last_scanned,compressed_name,compressed_name_detail,lossless_address,lossless_address_detail)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET name=excluded.name, folder_type=excluded.folder_type,
             file_count=excluded.file_count, child_folder_count=excluded.child_folder_count,
             last_scanned=excluded.last_scanned, compressed_name=excluded.compressed_name,
             compressed_name_detail=excluded.compressed_name_detail, lossless_address=excluded.lossless_address,
             lossless_address_detail=excluded.lossless_address_detail""",
        (fid, str(folder), folder.name, folder_type, len(files), len(children), created, now(),
         name_detail["code"], json.dumps(name_detail), lossless_detail["address"], json.dumps(lossless_detail)),
    )
    return fid


def upsert_file(conn: sqlite3.Connection, folder_id: str, path: Path) -> None:
    stat = path.stat()
    features = html_features(path)
    address = file_lossless_address(path)
    # classify_file is deterministic/local.  Do not call its separate ai_classify
    # fallback from this inventory-and-navigation tool.
    classification = classify_file(str(path), folder_class="")
    keywords = local_keywords(path, classification)
    proposal = propose_name({
        "name": path.name,
        "path": str(path),
        "ext": path.suffix.lower(),
        "mtime": stat.st_mtime,
        "chi_domain": classification.get("domain", {}).get("name", ""),
        "content_type": classification.get("content_type", inferred_type(path)),
        "chi_confidence": classification.get("confidence", 0.0),
        "sample": " ".join(keywords),
    })
    conn.execute(
        """INSERT INTO file_memory(file_id,folder_id,path,name,item_type,format,reading_level,
             has_topbar,has_audio,has_equations,has_claims,content_fingerprint,last_modified,size_bytes,last_scanned,
             lossless_address,lossless_address_detail,local_classification_json,keywords_json,keywords_text,proposed_name,proposed_name_detail,
             doc_type,type_confidence,type_scores_json,type_evidence_json,doc_type_scanned_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET folder_id=excluded.folder_id, name=excluded.name,
             item_type=excluded.item_type, format=excluded.format, has_topbar=excluded.has_topbar,
             has_audio=excluded.has_audio, has_equations=excluded.has_equations, has_claims=excluded.has_claims,
             content_fingerprint=excluded.content_fingerprint, last_modified=excluded.last_modified,
             size_bytes=excluded.size_bytes, last_scanned=excluded.last_scanned,
             lossless_address=excluded.lossless_address, lossless_address_detail=excluded.lossless_address_detail,
             local_classification_json=excluded.local_classification_json, keywords_json=excluded.keywords_json,
             keywords_text=excluded.keywords_text,
             proposed_name=excluded.proposed_name, proposed_name_detail=excluded.proposed_name_detail,
             doc_type=excluded.doc_type, type_confidence=excluded.type_confidence,
             type_scores_json=excluded.type_scores_json, type_evidence_json=excluded.type_evidence_json,
             doc_type_scanned_at=excluded.doc_type_scanned_at""",
        (item_id(path, "FIL"), folder_id, str(path), path.name, inferred_type(path), path.suffix.lower().lstrip(".") or "none",
         reading_level(path), *(int(v) for v in features.values()), file_hash(path),
         datetime.fromtimestamp(stat.st_mtime, UTC).replace(microsecond=0).isoformat(), stat.st_size, now(),
         address["address"], json.dumps(address), json.dumps(classification), json.dumps(keywords),
         ", ".join(keywords), proposal.get("proposed_name"), json.dumps(proposal),
         classification.get("doc_type", "UNSCANNED"), float(classification.get("type_confidence", 0.0) or 0.0),
         json.dumps(classification.get("type_scores", {})), json.dumps(classification.get("type_evidence", [])), now()),
    )


DOC_TYPE_SAMPLE_BYTES = 20000

# Extensions whose bytes are worth reading as document text. Anything else is
# typed UNTYPED rather than guessed at.
DOC_TYPE_TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".rst", ".log", ".html", ".htm",
    ".json", ".yaml", ".yml", ".csv", ".tex", ".lean",
}


def backfill_doc_types(conn: sqlite3.Connection, limit: int = 0, force: bool = False,
                       path_prefix: str = "", verbose: bool = True) -> dict:
    """
    Second-axis pass over files ALREADY in the registry.

    Reads each recorded path, scores its document type, and writes the result
    to the dedicated columns plus the stored classification JSON. It does not
    re-walk the tree and does not touch any other registry field.
    """
    where, params = [], []
    if not force:
        where.append("(doc_type IS NULL OR doc_type = 'UNSCANNED')")
    if path_prefix:
        where.append("path LIKE ?")
        params.append(f"{path_prefix}%")
    sql = "SELECT file_id, path, name, local_classification_json FROM file_memory"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY path"
    if limit:
        sql += f" LIMIT {int(limit)}"

    # The connection may arrive with any row factory; this pass reads by name.
    prior_factory    = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.row_factory = prior_factory

    stats = {"considered": len(rows), "typed": 0, "untyped": 0, "missing": 0,
             "failed": 0, "chi_repaired": 0}
    if verbose:
        print(f"[doc-type] {len(rows)} file records to score")

    for i, row in enumerate(rows, 1):
        path = Path(row["path"])
        ext  = path.suffix.lower()
        result = None

        if ext not in DOC_TYPE_TEXT_EXTS:
            stats["untyped"] += 1
        else:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:DOC_TYPE_SAMPLE_BYTES]
                result = classify_document_type(text, name=path.name, path=str(path))
                stats["typed"] += 1
            except FileNotFoundError:
                # The registry outlives the file; record the gap, do not delete.
                stats["missing"] += 1
            except OSError:
                stats["failed"] += 1

        if result is None:
            result = {"doc_type": "UNTYPED" if ext not in DOC_TYPE_TEXT_EXTS else "UNREADABLE",
                      "type_confidence": 0.0, "type_scores": {}, "type_evidence": []}

        # keep the stored classification blob in step with the columns
        try:
            blob = json.loads(row["local_classification_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            blob = {}

        # Records written before local_classification_json existed carry no CHI
        # vector, which leaves them unplaceable in the visualisers. Repair those
        # in this same pass rather than forcing a full rescan of the tree.
        if "chi" not in blob:
            try:
                blob.update(classify_file(str(path), folder_class=""))
                stats["chi_repaired"] = stats.get("chi_repaired", 0) + 1
            except OSError:
                pass

        blob.update({k: result[k] for k in
                     ("doc_type", "type_confidence", "type_scores", "type_evidence")})

        conn.execute(
            """UPDATE file_memory SET doc_type=?, type_confidence=?, type_scores_json=?,
                 type_evidence_json=?, doc_type_scanned_at=?, local_classification_json=?
               WHERE file_id=?""",
            (result["doc_type"], float(result["type_confidence"]),
             json.dumps(result["type_scores"]), json.dumps(result["type_evidence"]),
             now(), json.dumps(blob), row["file_id"]),
        )
        if verbose and i % 500 == 0:
            print(f"[doc-type]   {i}/{len(rows)}")
            conn.commit()

    conn.commit()
    if verbose:
        print(f"[doc-type] typed={stats['typed']} untyped={stats['untyped']} "
              f"missing={stats['missing']} failed={stats['failed']}")
    return stats


def local_ai_enrichment(path: Path, model: str = "qwen3:4b-instruct") -> dict | None:
    """Ask the on-device model for retrieval metadata only, never a decision.

    The contract is intentionally narrow: source-bound tags and a one-sentence
    summary.  No filesystem action, truth evaluation, or canon status is asked
    for or accepted.
    """
    if path.suffix.lower() not in TEXT_KEYWORD_EXTENSIONS or path.stat().st_size > 2_000_000:
        return None
    try:
        excerpt = path.read_text(encoding="utf-8", errors="ignore")[:6_000]
    except OSError:
        return None
    prompt = (
        "You are a local file-indexing assistant. Return ONLY JSON with keys "
        "keywords (array, max 8), summary (one factual sentence), "
        "topic_phrases (array, max 5), confidence (number 0 to 1). "
        "Use only the supplied source excerpt. Do not decide truth, quality, "
        "canon status, authority, or any filesystem action.\n"
        f"filename: {path.name}\nexcerpt:\n{excerpt}"
    )
    try:
        body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                           "format": "json", "options": {"temperature": 0}}).encode("utf-8")
        request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            parsed = json.loads(json.loads(response.read().decode("utf-8")).get("response", "{}"))
    except Exception:
        return None
    keywords = parsed.get("keywords", [])
    topics = parsed.get("topic_phrases", [])
    if not isinstance(keywords, list) or not isinstance(topics, list) or not isinstance(parsed.get("summary"), str):
        return None
    return {
        "keywords": [str(value)[:120] for value in keywords[:8]],
        "summary": parsed["summary"][:600],
        "topic_phrases": [str(value)[:160] for value in topics[:5]],
        "confidence": parsed.get("confidence"),
        "boundary": "local retrieval enrichment only; no canon, truth, quality, or action decision",
    }


def enrich_local_ai(conn: sqlite3.Connection, limit: int, model: str) -> tuple[int, int]:
    """Enrich changed source records after the deterministic scan has committed."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM file_memory WHERE ai_source_fingerprint IS NULL OR ai_source_fingerprint != content_fingerprint "
        "ORDER BY last_modified DESC"
    ).fetchall()
    completed = failed = 0
    for row in rows:
        if completed + failed >= limit:
            break
        if Path(row["path"]).suffix.lower() not in TEXT_KEYWORD_EXTENSIONS:
            continue
        result = local_ai_enrichment(Path(row["path"]), model)
        if result is None:
            failed += 1
            continue
        conn.execute(
            "UPDATE file_memory SET ai_enrichment_json=?, ai_model=?, ai_reviewed_at=?, ai_source_fingerprint=? WHERE file_id=?",
            (json.dumps(result), model, now(), row["content_fingerprint"], row["file_id"]),
        )
        completed += 1
    conn.commit()
    return completed, failed


def compact_meta(record: sqlite3.Row) -> list[str]:
    return [
        "<!-- fis:meta",
        f"fis_schema: {SCHEMA}", f"folder_id: {record['folder_id']}",
        f"folder_name: {json.dumps(record['name'])}", f"folder_path: {json.dumps(record['path'])}",
        f"purpose: {json.dumps(record['purpose'])}", f"folder_type: {record['folder_type']}",
        f"domain: {record['domain']}", f"series: {json.dumps(record['series_name'])}",
        f"chain_steps: {record['chain_steps']}", f"status: {record['status']}",
        f"owner: {json.dumps(record['owner'])}", f"canonical_source: {str(bool(record['canonical_source'])).lower()}",
        f"parent_backbone: {json.dumps(record['parent_backbone'])}",
        f"file_count: {record['file_count']}", f"child_folder_count: {record['child_folder_count']}",
        f"created: {record['created_at']}", f"last_scanned: {record['last_scanned']}",
        f"compressed_name: {json.dumps(record['compressed_name'])}",
        f"lossless_address: {json.dumps(record['lossless_address'])}",
        "-->"
    ]


def render_note(conn: sqlite3.Connection, folder: Path) -> str:
    conn.row_factory = sqlite3.Row
    record = conn.execute("SELECT * FROM folder_memory WHERE path=?", (str(folder),)).fetchone()
    # The registry retains past observations for audit. The visible note shows
    # only files that are currently present and eligible for this folder scan.
    current_paths = {str(path) for path in direct_files(folder)}
    files = [
        row for row in conn.execute(
            "SELECT * FROM file_memory WHERE folder_id=? ORDER BY name COLLATE NOCASE", (record["folder_id"],)
        ).fetchall()
        if row["path"] in current_paths
    ]
    children = direct_children(folder)
    type_counts = Counter(row["format"] for row in files)
    formats = ", ".join(f"{fmt}:{count}" for fmt, count in sorted(type_counts.items())) or "none"
    code_detail = json.loads(record["compressed_name_detail"] or "{}")
    tags = code_detail.get("tags", [])
    tag_meanings = code_detail.get("tag_meanings", {})
    decoded_tags = ", ".join(f"{tag}={tag_meanings.get(tag, 'unresolved')}" for tag in tags) or "GN=general"
    code_explanation = " | ".join([
        f"{code_detail.get('domain', 'GN')}={code_detail.get('domain_meaning', 'general')}",
        f"{code_detail.get('ct', 'DOC')}=document content",
        f"tags: {decoded_tags}",
        f"{code_detail.get('status', 'AC')}={record['status']}",
    ])
    lines = compact_meta(record)
    lines += ["", f"# {record['name']}", "", f"> {record['purpose']}", "",
              "| Type | State | Files | Contents | Health | Last scanned |",
              "|---|---|---:|---|---|---|",
              f"| {record['folder_type']} | {record['status']} | {record['file_count']} | {formats} | unassessed | {record['last_scanned']} |",
              "", "## Compressed Folder Name", "",
              f"`{record['compressed_name']}`", "",
              f"{code_explanation}. This is a descriptor from `fis_namer.py`, not an approved rename.",
              "", "## Lossless Address", "", f"`{record['lossless_address']}`", "",
              "Python-derived from the folder title and local content sample. It does not call an AI, rewrite a source, or move anything.",
              f"Mode trigger: `{json.loads(record['lossless_address_detail'] or '{}').get('trigger') or 'none (LOSS mode)'}`.",
              "", "## Files here", "", "| File | Internal address | Type | Role | Presentation | Status |", "|---|---|---|---|---|---|"]
    for row in files:
        path = Path(row["path"])
        link = relative_link(folder, path)
        bits = []
        if row["has_topbar"]: bits.append("topbar")
        if row["has_audio"]: bits.append("audio")
        if row["has_equations"]: bits.append("math")
        if row["has_claims"]: bits.append("claims")
        presentation = ", ".join(bits) or "plain"
        lines += [f"| [{markdown_label(row['name'])}]({link}) | `{row['lossless_address']}` | {row['format']} | {row['item_type']} | {presentation} | {row['status']} |",
                  f"<!-- fis:file id=\"{row['file_id']}\" fingerprint=\"{row['content_fingerprint']}\" lossless_address=\"{row['lossless_address']}\" -->"]
    lines += ["", "## Child folders", "", "| Folder | Type | Files | Link |", "|---|---|---:|---|"]
    for child in children:
        child_record = conn.execute("SELECT folder_type,file_count FROM folder_memory WHERE path=?", (str(child),)).fetchone()
        child_type = child_record["folder_type"] if child_record else directory_kind(child)
        child_files = child_record["file_count"] if child_record else len(direct_files(child))
        link = relative_link(folder, child / ".fisnote")
        lines += [f"| {child.name} | {child_type} | {child_files} | [{markdown_label(child.name)}/]({link}) |",
                  f"<!-- fis:link path=\"{relative_link(folder, child)}\" rel=\"child\" -->"]
    lines += ["", "## Open context", "", "| Field | Current value |", "|---|---|",
              "| Purpose | UNRESOLVED until a human or NLP review supplies it. |",
              "| Domain / series / chain | UNCLASSIFIED. Do not infer canon status from filenames. |",
              "| Related copies | Query the registry by content fingerprint. |",
              "", "<!-- FIS folder-memory.v2: generated view. Edit registry fields, not this file. -->", ""]
    return "\n".join(lines)


def file_note_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.fisnote")


def render_file_note(row: sqlite3.Row) -> str:
    local = json.loads(row["local_classification_json"] or "{}")
    keywords = json.loads(row["keywords_json"] or "[]")
    domain = local.get("domain", {})
    law = local.get("law", {})
    proposal = json.loads(row["proposed_name_detail"] or "{}")
    fields = [
        ("file_id", row["file_id"]),
        ("path", row["path"]),
        ("internal_address", row["lossless_address"]),
        ("lossless_address", row["lossless_address"]),
        ("proposed_name", row["proposed_name"] or "UNRESOLVED"),
        ("filename_grammar", proposal.get("grammar_id", "UNRESOLVED")),
        ("domain_code", proposal.get("domain_code", "UNRESOLVED")),
        ("type_code", proposal.get("type_code", proposal.get("ct_code", "UNRESOLVED"))),
        ("format", row["format"]),
        ("role", row["item_type"]),
        ("status", row["status"]),
        ("sha256", row["content_fingerprint"]),
        ("size_bytes", row["size_bytes"]),
        ("modified_at", row["last_modified"]),
        ("scanned_at", row["last_scanned"]),
        ("keywords", ", ".join(keywords) or "none"),
        ("local_domain_signal", f"{domain.get('name', 'unclassified')} ({domain.get('score', 0)}/3)"),
        ("dominant_chi_signal", f"{local.get('chi_factor', 'none')} / {local.get('chi_name', 'unclassified')}"),
        ("local_law_signal", f"{law.get('name', 'unclassified')} ({law.get('score', 0)}/3)"),
        ("local_content_role", local.get("file_role", "unclassified")),
        ("classification_confidence", local.get("confidence", 0)),
    ]
    lines = [
        "<!-- fis:file-meta",
        "fis_schema: file-memory.v2",
        f"file_id: {row['file_id']}",
        f"source_path: {json.dumps(row['path'])}",
        f"source_fingerprint: {row['content_fingerprint']}",
        "-->",
        "",
        f"# FIS File Note: {row['name']}",
        "",
        "Generated metadata sidecar. It describes the source file and does not replace, rename, or move it.",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key, value in fields:
        lines.append(f"| {key} | `{str(value).replace('|', '/')}` |")
    lines += ["", f"<!-- {GENERATED_FILE_NOTE_MARKER}. Edit registry fields, not this file. -->", ""]
    return "\n".join(lines)


def write_file_notes(conn: sqlite3.Connection, folders: list[Path]) -> tuple[int, int]:
    written = skipped = 0
    for folder in folders:
        _, rows = live_file_rows(conn, folder)
        for row in rows:
            note = file_note_path(Path(row["path"]))
            existing = note.read_text(encoding="utf-8", errors="ignore") if note.exists() else ""
            if existing and GENERATED_FILE_NOTE_MARKER not in existing:
                skipped += 1
                continue
            note.write_text(render_file_note(row), encoding="utf-8")
            written += 1
    return written, skipped


def cleanup_stale_file_notes(folders: list[Path]) -> int:
    removed = 0
    for folder in folders:
        for note in folder.glob("*.fisnote"):
            if note.name == ".fisnote" or note.name.startswith(".fisnote.legacy."):
                continue
            try:
                existing = note.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if GENERATED_FILE_NOTE_MARKER not in existing:
                continue
            source_name = note.name[:-len(".fisnote")]
            if not (folder / source_name).exists():
                note.unlink()
                removed += 1
    return removed


def wipe_existing_fisnotes(root: Path) -> int:
    removed = 0
    folders = [root]
    folders.extend(path for path in root.rglob("*") if path.is_dir())
    for folder in folders:
        if any(part.lower() in IGNORED_DIRS for part in folder.parts):
            continue
        folder_note = folder / ".fisnote"
        if folder_note.exists() and folder_note.is_file():
            folder_note.unlink()
            removed += 1
    for note in root.rglob("*.fisnote"):
        if any(part.lower() in IGNORED_DIRS for part in note.parts):
            continue
        if not note.is_file():
            continue
        note.unlink()
        removed += 1
    return removed


def live_file_rows(conn: sqlite3.Connection, folder: Path) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
    conn.row_factory = sqlite3.Row
    record = conn.execute("SELECT * FROM folder_memory WHERE path=?", (str(folder),)).fetchone()
    current_paths = {str(path) for path in direct_files(folder)}
    rows = [
        row for row in conn.execute(
            "SELECT * FROM file_memory WHERE folder_id=? ORDER BY name COLLATE NOCASE", (record["folder_id"],)
        ).fetchall()
        if row["path"] in current_paths
    ]
    return record, rows


def file_dossier_path(folder: Path, row: sqlite3.Row) -> Path:
    return folder / ".fis" / "files" / f"{row['file_id']}.html"


def file_link_count(path: Path) -> int:
    """Count explicit local link syntax only; this is not semantic relatedness."""
    if path.suffix.lower() not in {".md", ".txt", ".html", ".htm", ".json"} or path.stat().st_size > 2_000_000:
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:250_000]
    except OSError:
        return 0
    return len(re.findall(r"\[\[[^\]]+\]\]|\[[^\]]+\]\([^)]+\)|href\s*=", text, flags=re.I))


def folder_scores(folder: Path, files: list[sqlite3.Row]) -> list[dict[str, object]]:
    """Deterministic folder signals with evidence links, never a canon verdict."""
    now_ts = datetime.now().timestamp()
    facts = []
    for row in files:
        path = Path(row["path"])
        age_days = max(0, (now_ts - path.stat().st_mtime) / 86400)
        references = file_link_count(path)
        presentation = sum(int(row[field]) for field in ("has_topbar", "has_audio", "has_equations", "has_claims"))
        file_score = min(100, round(20 + min(30, path.stat().st_size / 5_000) + min(25, references * 2) + presentation * 6 + (15 if age_days <= 30 else 0)))
        facts.append({"row": row, "age_days": age_days, "references": references, "presentation": presentation, "file_score": file_score})
    count = len(facts)
    recent = [item for item in facts if item["age_days"] <= 30]
    distinct_days = len({Path(item["row"]["path"]).stat().st_mtime_ns // 86_400_000_000_000 for item in facts})
    activity = min(100, round(min(45, len(recent) * 8) + min(40, distinct_days * 4) + (15 if recent else 0)))
    depth = min(100, round(min(70, count * 4) + min(30, sum(Path(item["row"]["path"]).stat().st_size for item in facts) / 300_000 * 30)))
    connections = min(100, round(min(100, sum(item["references"] for item in facts) * 5)))
    richness = min(100, round((sum(item["presentation"] for item in facts) / max(1, count * 4)) * 100))
    registry = round(100 * sum(bool(item["row"]["content_fingerprint"] and item["row"]["lossless_address"]) for item in facts) / max(1, count))
    prevalence = round(activity * .30 + depth * .25 + connections * .20 + richness * .10 + registry * .15)
    top_activity = sorted(facts, key=lambda item: item["age_days"])[:5]
    top_connections = sorted(facts, key=lambda item: item["references"], reverse=True)[:5]
    top_richness = sorted(facts, key=lambda item: item["presentation"], reverse=True)[:5]
    return [
        {"label": "Folder signal", "score": prevalence, "description": "Composite navigation signal; not truth, quality, or canon status.", "evidence": sorted(facts, key=lambda item: item["file_score"], reverse=True)[:5]},
        {"label": "Activity", "score": activity, "description": f"{len(recent)} files modified in the last 30 days; {distinct_days} observed modification days.", "evidence": top_activity},
        {"label": "Depth", "score": depth, "description": f"{count} direct source files and {sum(Path(item['row']['path']).stat().st_size for item in facts):,} source bytes.", "evidence": sorted(facts, key=lambda item: Path(item["row"]["path"]).stat().st_size, reverse=True)[:5]},
        {"label": "Explicit links", "score": connections, "description": "Counts visible Markdown/wiki/HTML link syntax only; it does not infer semantic relationships.", "evidence": top_connections},
        {"label": "Presentation", "score": richness, "description": "Topbar, audio, equations, and claim-marker coverage in directly stored HTML files.", "evidence": top_richness},
        {"label": "Registry", "score": registry, "description": "Files with both a SHA-256 content fingerprint and lossless internal address.", "evidence": facts[:5]},
    ]


def render_score_tiles(folder: Path, scores: list[dict[str, object]]) -> str:
    tiles = []
    for score in scores:
        evidence = []
        for item in score["evidence"]:
            row = item["row"]
            href = escape(f"#{row['file_id']}", quote=True)
            evidence.append(f"<li><a href=\"{href}\">{escape(row['name'])}</a> <code>{item['file_score']}/100</code></li>")
        tiles.append(
            f"<details class=\"score-tile\"><summary><strong>{score['score']}</strong><span>{escape(str(score['label']))}</span></summary>"
            f"<p>{escape(str(score['description']))}</p><ul>{''.join(evidence) or '<li>No file evidence.</li>'}</ul></details>"
        )
    return "<section id=\"scores\"><h2>Folder Signals</h2><p class=\"muted\">Open a block to see the calculation evidence; file links jump to the inline machine block above.</p><div class=\"score-grid\">" + "".join(tiles) + "</div></section>"


def render_file_html(folder: Path, row: sqlite3.Row) -> str:
    """A generated file dossier. It describes a source; it never replaces it."""
    source = Path(row["path"])
    source_link = relative_link(file_dossier_path(folder, row).parent, source)
    local = json.loads(row["local_classification_json"] or "{}")
    keywords = json.loads(row["keywords_json"] or "[]")
    ai = json.loads(row["ai_enrichment_json"] or "{}")
    domain = local.get("domain", {})
    law = local.get("law", {})
    fields = [
        ("FIS file ID", row["file_id"]), ("Lossless address", row["lossless_address"]),
        ("Proposed compressed name", row["proposed_name"] or "UNRESOLVED"),
        ("Source fingerprint", row["content_fingerprint"]), ("Source path", row["path"]),
        ("Type / format", f"{row['item_type']} / {row['format']}"),
        ("Domain", row["domain"]), ("Series", row["series_name"] or "UNRESOLVED"),
        ("Chain steps", row["chain_steps"]), ("Reading level", row["reading_level"]),
        ("Canonical", str(bool(row["canonical"])).lower()), ("Superseded by", row["superseded_by"] or "none"),
        ("Node count", row["node_count"] if row["node_count"] is not None else "unscanned"),
        ("Lifecycle", row["status"]), ("Last modified", row["last_modified"]),
        ("Size", f"{row['size_bytes']} bytes"), ("Last scanned", row["last_scanned"]),
        ("Retrieval keywords", ", ".join(keywords) or "none found"),
        ("Local domain signal", f"{domain.get('name', 'unclassified')} ({domain.get('score', 0)}/3)"),
        ("Dominant CHI signal", f"{local.get('chi_factor', 'none')} / {local.get('chi_name', 'unclassified')}"),
        ("Local law signal", f"{law.get('name', 'unclassified')} ({law.get('score', 0)}/3)"),
        ("Local content role", local.get("file_role", "unclassified")),
        ("Evidence-term density", f"{local.get('evidence', 0)}/100"),
        ("Local classification confidence", local.get("confidence", 0)),
        ("Local AI keywords", ", ".join(ai.get("keywords", [])) or "not reviewed"),
        ("Local AI source summary", ai.get("summary", "not reviewed")),
        ("Local AI topics", ", ".join(ai.get("topic_phrases", [])) or "not reviewed"),
        ("Local AI model / reviewed", f"{row['ai_model'] or 'not reviewed'} / {row['ai_reviewed_at'] or 'not reviewed'}"),
    ]
    presentation = ", ".join(label for field, label in (("has_topbar", "topbar"), ("has_audio", "audio"), ("has_equations", "equations"), ("has_claims", "claims")) if row[field]) or "plain"
    rows = "".join(f"<tr><th>{escape(key)}</th><td><code>{escape(str(value or 'UNRESOLVED'))}</code></td></tr>" for key, value in fields)
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>FIS File | {escape(row['name'])}</title><style>
:root{{color-scheme:dark;--bg:#0b0d10;--panel:#12161d;--line:#303946;--text:#e7edf5;--muted:#94a3b8;--accent:#d1a922}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}}main{{max-width:1050px;margin:auto;padding:30px}}h1{{font:600 30px Georgia,serif;margin:5px 0 8px}}.eyebrow,code{{font-family:ui-monospace,Consolas,monospace}}.eyebrow{{color:var(--accent);font-size:12px;letter-spacing:1px}}.muted{{color:var(--muted)}}a{{color:#72b7ff;text-decoration:none}}a:hover{{text-decoration:underline}}.actions{{display:flex;gap:10px;margin:18px 0}}.actions a{{border:1px solid var(--line);padding:8px 10px;background:var(--panel)}}table{{width:100%;border-collapse:collapse;background:var(--panel)}}th,td{{border:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}}th{{width:190px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}}code{{word-break:break-word;color:#d6e5f5}}@media(max-width:700px){{main{{padding:16px}}th{{width:120px}}}}
</style></head><body><main><div class=\"eyebrow\">FIS FILE DOSSIER / GENERATED VIEW</div><h1>{escape(row['name'])}</h1><p class=\"muted\">Classification interior for one source file. Unresolved fields remain visible rather than guessed.</p><div class=\"actions\"><a href=\"{escape(relative_link(file_dossier_path(folder, row).parent, folder / FIS_HTML_FILENAME), quote=True)}\">Back to folder</a><a href=\"{escape(source_link, quote=True)}\">Open original source</a></div><h2>All current classification fields</h2><table><tbody>{rows}<tr><th>Presentation markers</th><td><code>{escape(presentation)}</code></td></tr></tbody></table><p class=\"muted\">Generated from the FIS registry. This dossier does not alter or duplicate the source.</p></main></body></html>"""


def render_inline_file_block(folder: Path, row: sqlite3.Row) -> str:
    path = Path(row["path"])
    source_link = relative_link(folder, path)
    keywords = json.loads(row["keywords_json"] or "[]")
    local = json.loads(row["local_classification_json"] or "{}")
    chi = local.get("chi", {})
    domain = local.get("domain", {})
    law = local.get("law", {})
    features = ", ".join(label for field, label in (("has_topbar", "topbar"), ("has_audio", "audio"), ("has_equations", "math"), ("has_claims", "claims")) if row[field]) or "plain"
    chi_text = ", ".join(f"{key}:{value}" for key, value in chi.items() if value) or "none"
    meq_name = meq_namer_string(chi)
    meq_short = meq_namer_short(chi)
    has_lossless = bool(row["lossless_address"])
    lossless_color = "color:#d1a922" if has_lossless else "color:#94a3b8"
    fields = [
        ("MEQ Name", meq_name or "UNSCORED"),
        ("Internal address", row["lossless_address"]),
        ("Proposed compressed name", row["proposed_name"] or "UNRESOLVED"),
        ("SHA-256", row["content_fingerprint"]),
        ("Source path", row["path"]),
        ("Type / format", f"{row['item_type']} / {row['format']}"),
        ("Presentation", features),
        ("Keywords", ", ".join(keywords) or "none"),
        ("Domain signal", f"{domain.get('name', 'unclassified')} ({domain.get('score', 0)}/3)"),
        ("Dominant CHI", f"{local.get('chi_factor', 'none')} / {local.get('chi_name', 'unclassified')}"),
        ("CHI vector", chi_text),
        ("Law signal", f"{law.get('name', 'unclassified')} ({law.get('score', 0)}/3)"),
        ("Content role", local.get("file_role", "unclassified")),
        ("Evidence density", f"{local.get('evidence', 0)}/100"),
        ("Confidence", local.get("confidence", 0)),
        ("Status", row["status"]),
        ("Last modified", row["last_modified"]),
        ("Last scanned", row["last_scanned"]),
        ("Size", f"{row['size_bytes']} bytes"),
    ]
    location_row = (
        f"<tr><th>Open source location</th><td><a href=\"{escape(source_link, quote=True)}\">"
        f"{escape(row['path'])}</a></td></tr>"
    )
    machine_rows = location_row + "".join(
        f"<tr><th>{escape(label)}</th><td><code>{escape(str(value or 'UNRESOLVED'))}</code></td></tr>"
        for label, value in fields
    )
    search_blob = " ".join(str(value or "") for _, value in fields)
    # Lossless button: gold if present, muted if not
    lossless_btn = (
        f"<span class=\"lossless-btn\" style=\"{lossless_color};cursor:pointer;font-size:11px\" "
        f"title=\"{escape(row['lossless_address'] or 'no lossless address', quote=True)}\">"
        f"{'◆' if has_lossless else '◇'} lossless</span>"
    )
    return (
        f"<details id=\"{escape(row['file_id'], quote=True)}\" class=\"file-block\" data-search=\"{escape((row['name'] + ' ' + search_blob + ' ' + (meq_name or '')).lower(), quote=True)}\">"
        f"<summary><span class=\"file-name\">{escape(row['name'])}</span>"
        f"<code class=\"meq-tag\" style=\"font-size:10px;color:#f1d37a\">{escape(meq_short)}</code>"
        f"<span>{escape(row['format'])}</span><span>{escape(row['item_type'])}</span>"
        f"<span>{escape(', '.join(keywords[:6])) or 'none'}</span>"
        f"{lossless_btn}"
        f"<a class=\"source-link\" href=\"{escape(source_link, quote=True)}\">source</a></summary>"
        f"<div class=\"machine\"><table><tbody>{machine_rows}</tbody></table></div></details>"
    )


def descriptor_verification(record: sqlite3.Row) -> str:
    detail = json.loads(record["compressed_name_detail"] or "{}")
    tags = detail.get("tags", [])
    tag_meanings = detail.get("tag_meanings", {})
    decoded_tags = ", ".join(f"{tag}={tag_meanings.get(tag, 'unresolved')}" for tag in tags) or "GN=general"
    return " | ".join([
        f"domain {detail.get('domain', 'GN')}={detail.get('domain_meaning', 'general')}",
        f"type {detail.get('ct', 'DOC')}",
        f"tags {decoded_tags}",
        f"date {detail.get('date', '00000000')}",
        f"status {detail.get('status', record['status'])}",
        f"lossless {record['lossless_address'] or 'UNRESOLVED'}",
    ])


def declared_master_equation_identity(folder: Path) -> dict[str, str] | None:
    """Read a local MEQ identity declaration instead of inferring it from tags."""
    candidates = [
        path for path in direct_files(folder)
        if "master_equation" in path.stem.lower() or "master equation" in path.stem.lower()
    ]
    for path in candidates:
        if path.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:100_000]
        except OSError:
            continue
        if "MASTER_EQUATION_CHI" not in text:
            continue
        address_match = re.search(
            r"(?m)^ADDRESS\s*=\s*\n?\s*([^\n]+)(?:\n\s*::\s*([^\n]+))?(?:\n\s*::\s*([^\n]+))?",
            text,
        )
        address = address_match.group(1).strip() if address_match else "THEOPHYSICS_FORMAL/MASTER_EQUATION_CHI/UNRESOLVED"
        vector = address_match.group(2).strip() if address_match and address_match.group(2) else "UNRESOLVED_VECTOR"
        coupling = address_match.group(3).strip() if address_match and address_match.group(3) else "UNRESOLVED_COUPLING"
        return {
            "name": "MASTER_EQUATION_CHI__CANONICAL_LOCAL_AND_INTEGRATED_FORM__R3",
            "address": address,
            "vector": vector,
            "coupling": coupling,
            "source": path.name,
        }
    return None


def master_equation_identity(folder: Path, record: sqlite3.Row) -> dict[str, str] | None:
    declared = declared_master_equation_identity(folder)
    if not declared and "master eq" not in folder.name.lower() and "master equation" not in folder.name.lower():
        return None
    declared = declared or {
        "name": "MASTER_EQUATION_CHI__CANONICAL_LOCAL_AND_INTEGRATED_FORM__R3",
        "address": "THEOPHYSICS_FORMAL/MASTER_EQUATION_CHI/CANONICAL_LOCAL_AND_INTEGRATED_FORM/AI_INTERNAL_REVIEW/BIND/R3",
        "vector": "G3 M3 E3 S3 T3 K3 R3 Q3 F3 C3",
        "coupling": "[G.C] [M.F] [E.Q] [S.R] [T.K]",
        "source": "folder-name fallback",
    }
    return {
        "name": declared["name"],
        "verification": (
            f"Nabla address {declared['address']} :: {declared['vector']} :: {declared['coupling']} "
            f"| declared by {declared['source']} "
            f"| FIS descriptor {record['compressed_name'] or 'UNRESOLVED'} "
            f"| lossless {record['lossless_address'] or 'UNRESOLVED'}"
        ),
    }


def render_semantic_network(files: list) -> str:
    """Build an interactive semantic network showing how files connect via shared keywords."""
    if not files:
        return ""
    # Build keyword → file_ids map
    kw_to_files = {}
    file_labels = {}
    for row in files:
        fid = row["file_id"]
        file_labels[fid] = row["name"]
        keywords = json.loads(row["keywords_json"] or "[]")
        local = json.loads(row["local_classification_json"] or "{}")
        chi_factor = local.get("chi_factor", "")
        chi_name = local.get("chi_name", "")
        domain = local.get("domain", {}).get("name", "")
        law = local.get("law", {}).get("name", "")
        # Use keywords + domain + chi + law as connection signals
        tags = set(keywords[:10])
        if chi_factor and chi_factor != "none": tags.add(chi_factor)
        if chi_name and chi_name != "unclassified": tags.add(chi_name)
        if domain and domain != "unknown": tags.add(domain)
        if law and law != "none": tags.add(law)
        for tag in tags:
            kw_to_files.setdefault(tag.lower(), []).append(fid)
    # Find connections: files that share 2+ tags
    from collections import defaultdict
    edges = defaultdict(int)
    shared_tags = defaultdict(list)
    for tag, fids in kw_to_files.items():
        if len(fids) < 2 or len(fids) > len(files) * 0.8:
            continue  # skip tags that are too common (noise) or singleton
        for i in range(len(fids)):
            for j in range(i + 1, len(fids)):
                pair = tuple(sorted([fids[i], fids[j]]))
                edges[pair] += 1
                if len(shared_tags[pair]) < 5:
                    shared_tags[pair].append(tag)
    # Only keep edges with 2+ shared tags
    strong = {pair: count for pair, count in edges.items() if count >= 2}
    if not strong:
        return '<section id="relationships"><h2>Semantic Network</h2><p class="muted">No strong keyword connections found between files in this folder.</p></section>'
    # Build cluster summary: group by dominant tag
    cluster_counts = Counter()
    for tag, fids in kw_to_files.items():
        if 2 <= len(fids) <= len(files) * 0.8:
            cluster_counts[tag] += len(fids)
    top_clusters = cluster_counts.most_common(15)
    # Render as a connection table
    rows_html = []
    for (a, b), count in sorted(strong.items(), key=lambda x: -x[1])[:30]:
        name_a = escape(file_labels.get(a, a)[:40])
        name_b = escape(file_labels.get(b, b)[:40])
        tags_str = escape(", ".join(shared_tags.get((a, b), [])[:4]))
        rows_html.append(
            f'<tr><td><a href="#{escape(a, quote=True)}">{name_a}</a></td>'
            f'<td><a href="#{escape(b, quote=True)}">{name_b}</a></td>'
            f'<td>{count}</td><td>{tags_str}</td></tr>'
        )
    cluster_badges = " ".join(
        f'<span class="badge">{escape(tag)} ({count})</span>'
        for tag, count in top_clusters
    )
    return (
        f'<section id="relationships"><h2>Semantic Network</h2>'
        f'<p class="section-note">Connections based on shared keywords, CHI variables, domain, and law signals. '
        f'Files sharing 2+ tags are linked.</p>'
        f'<div class="badges" style="margin:8px 0">{cluster_badges}</div>'
        f'<table class="signal-table"><thead><tr><th>File A</th><th>File B</th><th>Shared</th><th>Via</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table></section>'
    )


def folder_meq_aggregate(files: list) -> str:
    """Compute aggregate MEQ vector for the folder from all file CHI vectors."""
    totals = {var: 0 for var in "G M E S T K R Q F C".split()}
    count = 0
    for row in files:
        local = json.loads(row["local_classification_json"] or "{}")
        chi = local.get("chi", {})
        if chi and any(chi.values()):
            for var in totals:
                totals[var] += int(chi.get(var, 0))
            count += 1
    if count == 0:
        return ""
    avg = {var: min(3, round(totals[var] / count)) for var in totals}
    return meq_namer_string(avg)


def render_semantic_capsule(record: sqlite3.Row, files: list, children: list, formats: dict) -> str:
    """Human-readable summary of the folder — also doubles as the SQLite summary row."""
    total_bytes = sum(Path(row["path"]).stat().st_size for row in files if Path(row["path"]).exists())
    fmt_str = ", ".join(f"{count} {fmt}" for fmt, count in sorted(formats.items())) or "empty"
    # Dominant CHI signal across files
    chi_counts = Counter()
    for row in files:
        local = json.loads(row["local_classification_json"] or "{}")
        cf = local.get("chi_factor", "")
        cn = local.get("chi_name", "")
        if cf and cf != "none":
            chi_counts[f"{cf} / {cn}"] += 1
    dominant = chi_counts.most_common(1)[0][0] if chi_counts else "none"
    domain_counts = Counter()
    for row in files:
        local = json.loads(row["local_classification_json"] or "{}")
        d = local.get("domain", {})
        dn = d.get("name", "unclassified") if isinstance(d, dict) else "unclassified"
        if dn != "unknown":
            domain_counts[dn] += 1
    dom_str = domain_counts.most_common(1)[0][0] if domain_counts else "unclassified"
    summary = (
        f"{record['folder_type'].capitalize()} folder holding {len(files)} file(s) "
        f"({total_bytes:,} bytes) and {len(children)} child folder(s). "
        f"Dominant signal {dominant}; domain {dom_str}."
    )
    return (
        f'<section id="semantic"><h2>Semantic Capsule</h2>'
        f'<div class="capsule"><p>{escape(summary)}</p></div></section>'
    )


def render_health_checklist(record: sqlite3.Row, files: list) -> str:
    """Health checklist — shows what still needs human decisions."""
    items = []
    if record["purpose"] == "UNRESOLVED":
        items.append(("warn", "Purpose", "UNRESOLVED"))
    else:
        items.append(("ok", "Purpose", record["purpose"]))
    if record["owner"] == "UNRESOLVED":
        items.append(("warn", "Owner", "UNRESOLVED"))
    if not record["canonical_source"]:
        items.append(("warn", "Canonical source", "not set"))
    unclassified = sum(1 for r in files if r["status"] == "unclassified")
    if unclassified:
        items.append(("warn", "Unclassified files", f"{unclassified} of {len(files)}"))
    else:
        items.append(("ok", "All files classified", f"{len(files)} of {len(files)}"))
    presentation = sum(1 for r in files if any(r[f] for f in ("has_topbar", "has_audio", "has_equations", "has_claims")))
    items.append(("ok" if presentation else "warn", "Presentation coverage", f"{presentation} of {len(files)}"))
    li = "".join(
        f'<li class="{cls}">{escape(label)}<code>{escape(str(value))}</code></li>'
        for cls, label, value in items
    )
    return f'<section id="health"><h2>Health</h2><ul class="health-list">{li}</ul></section>'


def render_json_island(record: sqlite3.Row, files: list, children: list, scores: list, folder_meq: str) -> str:
    """Single machine-readable JSON block for the SQLite scanner."""
    def parse_detail(row, field):
        try:
            return json.loads(row[field] or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    file_records = []
    for row in files:
        local = json.loads(row["local_classification_json"] or "{}")
        chi = local.get("chi", {})
        keywords = json.loads(row["keywords_json"] or "[]")
        domain = local.get("domain", {})
        law = local.get("law", {})
        meq = meq_namer_string(chi)
        file_records.append({
            "file_id": row["file_id"],
            "name": row["name"],
            "source_path": row["path"],
            "meq_name": meq,
            "internal_address": row["lossless_address"],
            "proposed_compressed_name": row["proposed_name"],
            "sha256": row["content_fingerprint"],
            "type": row["item_type"],
            "format": row["format"],
            "keywords": keywords[:20],
            "domain_signal": f"{domain.get('name', 'unclassified')} ({domain.get('score', 0)}/3)" if isinstance(domain, dict) else str(domain),
            "dominant_chi": f"{local.get('chi_factor', 'none')} / {local.get('chi_name', 'unclassified')}",
            "chi_vector": {k: v for k, v in chi.items() if v},
            "law_signal": f"{law.get('name', 'unclassified')} ({law.get('score', 0)}/3)" if isinstance(law, dict) else str(law),
            "content_role": local.get("file_role", "unclassified"),
            "evidence_density": local.get("evidence", 0),
            "confidence": local.get("confidence", 0),
            "status": row["status"],
            "last_modified": row["last_modified"],
            "last_scanned": row["last_scanned"],
            "size_bytes": row["size_bytes"],
        })

    child_records = []
    for child_path in children:
        cr = {"name": child_path.name, "type": directory_kind(child_path), "file_count": len(direct_files(child_path))}
        child_records.append(cr)

    signal_map = {s["label"].lower().replace(" ", "_"): s["score"] for s in scores}

    island = {
        "schema": "fis.folder/2.1",
        "folder": {
            "folder_id": record["folder_id"],
            "path": record["path"],
            "name": record["name"],
            "folder_type": record["folder_type"],
            "purpose": record["purpose"],
            "domain": record["domain"],
            "status": record["status"],
            "owner": record["owner"],
            "canonical_source": record["canonical_source"],
            "file_count": record["file_count"],
            "child_folder_count": record["child_folder_count"],
            "created_at": record["created_at"],
            "last_scanned": record["last_scanned"],
            "compressed_name": record["compressed_name"],
            "compressed_name_detail": parse_detail(record, "compressed_name_detail"),
            "lossless_address": record["lossless_address"],
            "lossless_address_detail": parse_detail(record, "lossless_address_detail"),
            "meq_aggregate": folder_meq,
        },
        "files": file_records,
        "child_folders": child_records,
        "signals": signal_map,
    }
    return f'<script type="application/json" id="fis-folder-record">\n{json.dumps(island, indent=2, ensure_ascii=False)}\n</script>'


def render_html(conn: sqlite3.Connection, folder: Path) -> str:
    """Static, local-file-friendly index. It is a view, never source content."""
    record, files = live_file_rows(conn, folder)
    children = direct_children(folder)
    formats = Counter(row["format"] for row in files)
    count_text = " | ".join(f"{escape(fmt)}: {count}" for fmt, count in sorted(formats.items())) or "none"
    file_blocks = [render_inline_file_block(folder, row) for row in files]
    meq_identity = master_equation_identity(folder, record)
    descriptor = meq_identity["name"] if meq_identity else (record["compressed_name"] or "UNRESOLVED")
    verification = meq_identity["verification"] if meq_identity else descriptor_verification(record)
    child_rows = []
    sidebar_children = []
    for child in children:
        child_record = conn.execute("SELECT folder_type,file_count,lossless_address FROM folder_memory WHERE path=?", (str(child),)).fetchone()
        child_type = child_record["folder_type"] if child_record else directory_kind(child)
        child_count = child_record["file_count"] if child_record else len(direct_files(child))
        child_address = child_record["lossless_address"] if child_record else "unscanned"
        child_page = child / FIS_HTML_FILENAME
        child_view = (
            f"<a href=\"{escape(relative_link(folder, child_page), quote=True)}\">open</a>"
            if child_page.exists() else "scan pending"
        )
        child_rows.append(
            f"<tr><td>{escape(child.name)}</td><td>{escape(child_type)}</td><td>{child_count}</td>"
            f"<td><code>{escape(child_address)}</code></td><td>{child_view}</td></tr>"
        )
        sidebar_children.append(
            f"<a class=\"child\" href=\"{escape(relative_link(folder, child_page), quote=True)}\">{escape(child.name)}</a>"
            if child_page.exists() else f"<span class=\"child pending\">{escape(child.name)} <small>pending</small></span>"
        )
    # Folder-level MEQ aggregate, semantic network, capsule, health, JSON island
    folder_meq = folder_meq_aggregate(files)
    semantic_html = render_semantic_network(files)
    scores_data = folder_scores(folder, files)
    score_html = render_score_tiles(folder, scores_data)
    capsule_html = render_semantic_capsule(record, files, children, formats)
    health_html = render_health_checklist(record, files)
    json_island = render_json_island(record, files, children, scores_data, folder_meq)
    # Breadcrumb: parent link for recursive navigation
    parent_link = f'<nav class="crumbs"><a href="../{FIS_HTML_FILENAME}">&#8593; {escape(folder.parent.name)}</a><span>/</span>{escape(record["name"])}</nav>'
    # UNRESOLVED chip
    purpose_html = f'<p><span class="unresolved">UNRESOLVED</span></p>' if record["purpose"] == "UNRESOLVED" else f'<p class="muted">{escape(record["purpose"])}</p>'
    sidebar = "".join([
        f"<div class=\"side-title\">{escape(record['name'])}</div>",
        "<a href=\"#overview\">Overview</a><a href=\"#semantic\">Semantic capsule</a><a href=\"#health\">Health</a><a href=\"#files\">Files</a><a href=\"#folders\">Folders</a><a href=\"#relationships\">Relationships</a><a href=\"#scores\">Signals</a><a href=\"#context\">Audit context</a>",
        f"<div class=\"side-label\">Navigate</div><a class=\"child\" href=\"../{FIS_HTML_FILENAME}\">&#8593; {escape(folder.parent.name)}</a>",
        "<div class=\"side-label\">Child folders</div>",
        "".join(sidebar_children) or "<span class=\"child pending\">None</span>",
        "<div class=\"side-label\">Record</div><a href=\"#context\">Machine context</a>",
    ])
    return f"""<!doctype html>
<html lang=\"en\" data-fis-schema=\"2.1\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<meta name=\"fis-schema\" content=\"2.1\"><meta name=\"generator\" content=\"FIS folder-brain generator\">
<title>FIS | {escape(record['name'])}</title>
<style>
:root{{color-scheme:dark;--bg:#060708;--panel:#0c0f14;--panel2:#090b0f;--line:#222a35;--text:#e7edf5;--muted:#8b97a7;--accent:#d1a922;--accent2:#f1d37a;--link:#6ea8e8}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}}.layout{{max-width:1500px;margin:auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:24px;padding:28px}}main{{min-width:0}}
h1{{font:600 34px Georgia,serif;margin:5px 0 8px}}h2{{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:var(--accent);margin-top:28px}}
.eyebrow,code{{font-family:ui-monospace,Consolas,monospace}}.eyebrow{{color:var(--accent);font-size:12px;letter-spacing:1px}}.muted{{color:var(--muted)}}
.identity{{border-left:3px solid var(--accent);padding:8px 0 8px 12px;margin:8px 0 10px;background:linear-gradient(90deg,rgba(209,169,34,.08),transparent)}}.identity code{{display:block;font-size:15px;color:var(--accent2);margin-bottom:4px}}.identity span{{display:block;color:var(--muted);font-size:12px}}
.crumbs{{font:12px ui-monospace,Consolas,monospace;color:var(--muted);margin-bottom:10px}}.crumbs a{{color:var(--accent)}}.crumbs span{{margin:0 4px}}
.unresolved{{display:inline-block;border:1px solid var(--accent);color:var(--accent);padding:2px 10px;border-radius:3px;font:11px ui-monospace,Consolas,monospace;letter-spacing:1px}}
.sidebar{{position:sticky;top:20px;align-self:start;border:1px solid var(--line);background:var(--panel);padding:12px;max-height:calc(100vh - 40px);overflow:auto}}.sidebar a,.sidebar .child{{display:block;padding:7px 6px;border-bottom:1px solid #1a222d}}.side-title{{font:600 15px Georgia,serif;padding:4px 6px 12px;color:var(--text)}}.side-label{{color:var(--accent);font:10px ui-monospace,Consolas,monospace;letter-spacing:1px;text-transform:uppercase;padding:16px 6px 5px}}.pending{{color:var(--muted)}}small{{font-size:10px}}
.summary{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:7px;margin:14px 0}}.metric{{border:1px solid var(--line);padding:8px 9px;background:var(--panel)}}.metric b{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}}
.score-grid{{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px}}.score-tile{{margin:0;border:1px solid var(--line);background:var(--panel);min-height:104px;padding:10px}}.score-tile summary{{list-style:none;cursor:pointer}}.score-tile summary::-webkit-details-marker{{display:none}}.score-tile strong{{display:block;color:var(--accent);font:600 28px Georgia,serif}}.score-tile span{{font:11px ui-monospace,Consolas,monospace;text-transform:uppercase;color:var(--muted)}}.score-tile p{{font-size:12px;color:var(--muted)}}.score-tile ul{{padding-left:17px;font-size:12px}}
table{{width:100%;border-collapse:collapse;background:var(--panel)}}th,td{{border:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}}th{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}}a{{color:var(--link);text-decoration:none}}a:hover{{text-decoration:underline}}code{{font-size:12px;color:#d6e5f5;word-break:break-word}}
input[type=search]{{width:min(440px,100%);margin:0;padding:9px 10px;border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:3px}}.file-controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 8px}}button{{border:1px solid var(--line);background:var(--panel);color:var(--text);padding:8px 10px;border-radius:3px;cursor:pointer}}button:hover{{border-color:var(--accent)}}.file-list{{display:grid;gap:4px}}.file-block{{border:1px solid var(--line);background:var(--panel);padding:0}}.file-block summary{{display:grid;grid-template-columns:minmax(180px,1.5fr) minmax(140px,1.2fr) 50px 70px minmax(130px,1fr) 68px 50px;gap:6px;align-items:center;padding:7px 9px;list-style:none;cursor:pointer}}.file-block summary::-webkit-details-marker{{display:none}}.file-block[open] summary{{border-bottom:1px solid var(--line);background:var(--panel2)}}.file-name{{font-weight:600;color:var(--text)}}.source-link{{justify-self:end;font-size:12px}}.machine{{padding:8px 10px 10px}}.machine table{{background:var(--panel2)}}.machine th{{width:190px}}.machine td,.machine th{{padding:6px 8px}}.file-head{{display:grid;grid-template-columns:minmax(180px,1.5fr) minmax(140px,1.2fr) 50px 70px minmax(130px,1fr) 68px 50px;gap:6px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 4px;padding:0 10px}}
.actions{{display:flex;gap:6px;flex-wrap:wrap}}.actions button{{padding:5px 9px;font-size:12px}}
.capsule{{border:1px solid var(--line);background:var(--panel);padding:12px 14px}}.capsule p{{margin:6px 0}}
.health-list{{list-style:none;padding:0;margin:0;display:grid;gap:4px}}.health-list li{{border:1px solid var(--line);background:var(--panel);padding:8px 10px;font-size:13px}}.health-list li::before{{content:"◆ ";font-size:11px}}.health-list li.warn::before{{color:var(--accent)}}.health-list li.ok::before{{color:#5f7f6a}}.health-list code{{margin-left:6px}}
details{{border:1px solid var(--line);padding:10px;background:var(--panel)}}summary{{cursor:pointer;color:var(--muted)}}
@media(max-width:800px){{.layout{{display:block;padding:16px}}.sidebar{{position:relative;top:auto;max-height:none;margin-bottom:16px}}.summary{{grid-template-columns:repeat(2,1fr)}}table{{display:block;overflow:auto;white-space:nowrap}}}}
</style></head><body data-api-base=\"\"><div class=\"layout\"><aside class=\"sidebar\">{sidebar}</aside><main id=\"overview\">
{parent_link}
<div class=\"eyebrow\">FIS FOLDER BRAIN v2.1 / RECURSIVE SEMANTIC VIEW</div><h1>{escape(record['name'])}</h1>
<div class=\"identity\"><code>{escape(descriptor)}</code><span>{escape(verification)}</span></div>
{f'<div class="identity" style="margin-top:4px"><code style="color:var(--accent2);font-size:13px">{escape(folder_meq)}</code><span style="color:var(--muted);font-size:11px">Folder MEQ aggregate (avg CHI across {len(files)} files)</span></div>' if folder_meq else ''}
{purpose_html}
<div class=\"summary\"><div class=\"metric\"><b>Lossless Address</b><code>{escape(record['lossless_address'] or '')}</code></div><div class=\"metric\"><b>Contents</b>{count_text}</div><div class=\"metric\"><b>State</b>{escape(record['status'])} / {len(files)} files</div><div class=\"metric\"><b>Scan</b><code>{escape(record['last_scanned'] or '')}</code></div></div>
{capsule_html}
{health_html}
<details id=\"context\" style=\"margin-top:28px\"><summary>Machine context and audit fields</summary><pre>{escape(json.dumps(dict(record), indent=2, ensure_ascii=False))}</pre></details>
<h2 id=\"files\">Files Here</h2><div class=\"file-controls\"><input id=\"file-search\" type=\"search\" placeholder=\"Find by name, address, type, or keyword\" aria-label=\"Filter files\"><button id=\"toggle-files\" type=\"button\">Open all</button></div><div class=\"file-head\"><span>File</span><span>MEQ Vector</span><span>Format</span><span>Role</span><span>Keywords</span><span>Lossless</span><span>Open</span></div><div id=\"file-rows\" class=\"file-list\">{''.join(file_blocks)}</div>
<h2 id=\"folders\">Child Folders</h2><table><thead><tr><th>Folder</th><th>Type</th><th>Files</th><th>Address</th><th>View</th></tr></thead><tbody>{''.join(child_rows) or '<tr><td colspan="5" class="muted">No child folders.</td></tr>'}</tbody></table>{semantic_html}{score_html}
<p class=\"muted\" style=\"margin-top:24px\">Generated from the FIS registry. Source files remain in place; this page is an index, not a replacement.</p>
</main></div>
{json_island}
<script>
const q=document.getElementById('file-search');const blocks=[...document.querySelectorAll('.file-block')];q?.addEventListener('input',()=>{{const v=q.value.toLowerCase();blocks.forEach(b=>b.hidden=!(b.dataset.search+' '+b.innerText.toLowerCase()).includes(v));}});const toggle=document.getElementById('toggle-files');toggle?.addEventListener('click',()=>{{const visible=blocks.filter(b=>!b.hidden);const openSome=visible.some(b=>!b.open);visible.forEach(b=>b.open=openSome);toggle.textContent=openSome?'Close all':'Open all';}});document.querySelectorAll('.source-link').forEach(a=>a.addEventListener('click',e=>e.stopPropagation()));
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',()=>{{navigator.clipboard?.writeText(b.dataset.copy);b.textContent='Copied';setTimeout(()=>b.textContent=b.dataset.copy.startsWith('MEQ')?'Copy address':'Copy SHA-256',900);}}));
document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{{const payload={{file_id:b.dataset.fileId,target:b.dataset.target||null,folder:document.querySelector('h1').textContent}};if(window.FIS_API?.run){{window.FIS_API.run(b.dataset.action,payload);}}else{{b.textContent='API not connected';setTimeout(()=>b.textContent=b.dataset.action==='apply-name'?'Apply proposed name':'Mark reviewed',1100);}}}}))</script></body></html>"""


def folders_to_scan(root: Path, recursive: bool) -> Iterable[Path]:
    yield root
    if recursive:
        # os.walk does not follow directory junctions/symlinks by default. This
        # prevents a Desktop-wide scan from re-entering a linked ancestor.
        seen: set[str] = {os.path.normcase(os.path.abspath(str(root)))}
        for dirpath, dirnames, _filenames in os.walk(root, topdown=True, followlinks=False):
            dirnames[:] = [
                name for name in dirnames
                if name.lower() not in IGNORED_DIRS
                and not name.lower().startswith("#recycle")
                and not name.startswith(".")
            ]
            for name in dirnames:
                path = Path(dirpath) / name
                key = os.path.normcase(os.path.abspath(str(path)))
                if key in seen:
                    continue
                seen.add(key)
                yield path


def scan(
    root: Path,
    db_path: Path,
    recursive: bool,
    write: bool,
    html: bool,
    local_ai: bool,
    ai_limit: int,
    ai_model: str,
    file_notes: bool = False,
    cleanup_stale: bool = False,
    wipe_fisnotes: bool = False,
) -> tuple[int, int, int, int, int, int, int, int]:
    # Global output contract: recursive semantic HTML + SQLite only. Legacy
    # flags remain accepted for launcher compatibility but cannot write, wipe,
    # or clean up Markdown-like .fisnote artifacts.
    recursive = True
    html = True
    write = False
    file_notes = False
    cleanup_stale = False
    wipe_fisnotes = False
    wiped = 0
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    folders = []
    for folder in folders_to_scan(root, recursive):
        if folder.exists():
            folders.append(folder)
            if len(folders) % 500 == 0:
                print(f"[DISCOVER] {len(folders)} folders found; current={folder}", flush=True)
    print(f"[DISCOVER] complete; folders={len(folders)}", flush=True)
    indexed_folders: list[Path] = []
    unavailable_folders = 0
    for index, folder in enumerate(folders, 1):
        try:
            files, children = direct_files(folder), direct_children(folder)
        except OSError as exc:
            unavailable_folders += 1
            print(
                f"[SKIP] unavailable folder during indexing: {folder} "
                f"({exc.__class__.__name__}: {exc})",
                flush=True,
            )
            continue
        fid = upsert_folder(conn, folder, files, children)
        for file in files:
            upsert_file(conn, fid, file)
        indexed_folders.append(folder)
        if index % 25 == 0 or index == len(folders):
            print(f"[INDEX] {index}/{len(folders)} folders; current={folder}", flush=True)
    conn.commit()
    enriched = failed = 0
    if local_ai:
        enriched, failed = enrich_local_ai(conn, ai_limit, ai_model)
    if write:
        for folder in folders:
            note = folder / ".fisnote"
            existing = note.read_text(encoding="utf-8", errors="ignore") if note.exists() else ""
            if note.exists() and "fis_schema: folder-memory.v2" not in existing:
                backup = folder / f".fisnote.legacy.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(note, backup)
            note.write_text(render_note(conn, folder), encoding="utf-8")
    file_notes_written = file_notes_skipped = 0
    if file_notes:
        file_notes_written, file_notes_skipped = write_file_notes(conn, folders)
    if html:
        # Children first means the root sidebar only links to pages that exist.
        rendered_total = len(indexed_folders)
        for rendered, folder in enumerate(reversed(indexed_folders), 1):
            page = folder / FIS_HTML_FILENAME
            try:
                existing = page.read_text(encoding="utf-8", errors="ignore") if page.exists() else ""
                generated_markers = (
                    "FIS FOLDER BRAIN / STATIC LOCAL VIEW",
                    "FIS FOLDER BRAIN v2 / RECURSIVE SEMANTIC VIEW",
                )
                if existing and not any(marker in existing for marker in generated_markers):
                    raise RuntimeError(f"Refusing to overwrite non-generated page: {page}")
                page.write_text(render_html(conn, folder), encoding="utf-8")
            except OSError as exc:
                unavailable_folders += 1
                print(
                    f"[SKIP] unavailable folder during HTML generation: {folder} "
                    f"({exc.__class__.__name__}: {exc})",
                    flush=True,
                )
                continue
            if rendered % 25 == 0 or rendered == rendered_total:
                print(f"[HTML] {rendered}/{rendered_total} pages; current={page}", flush=True)
    if unavailable_folders:
        print(f"[SKIP] unavailable folder events={unavailable_folders}", flush=True)
    stale_removed = cleanup_stale_file_notes(folders) if cleanup_stale else 0
    conn.close()
    return (
        len(folders),
        sum(len(direct_files(folder)) for folder in folders),
        enriched,
        failed,
        file_notes_written,
        file_notes_skipped,
        stale_removed,
        wiped,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="FIS v2 recursive semantic HTML generator (HTML + SQLite only).")
    parser.add_argument("folder", type=Path, help="Folder to inventory")
    parser.add_argument("--db", type=Path, default=Path(__file__).with_name("fis_folder_memory.sqlite"))
    parser.add_argument("--tree", action="store_true", help="Compatibility flag; recursive scan is always enabled")
    parser.add_argument("--write", action="store_true", help="Deprecated compatibility flag; .fisnote writing is disabled")
    parser.add_argument("--file-notes", action="store_true", help="Deprecated compatibility flag; .fisnote writing is disabled")
    parser.add_argument("--cleanup-stale", action="store_true", help="Deprecated compatibility flag; .fisnote mutation is disabled")
    parser.add_argument("--wipe-fisnotes", action="store_true", help="Deprecated compatibility flag; .fisnote mutation is disabled")
    parser.add_argument("--html", action="store_true", help="Compatibility flag; recursive FIS.html output is always enabled")
    parser.add_argument("--local-ai", dest="local_ai", action="store_true", default=True,
                        help="After the deterministic scan, enrich changed text files with local Ollama proposals (default)")
    parser.add_argument("--no-local-ai", dest="local_ai", action="store_false",
                        help="Skip the local-Ollama proposal queue for this run")
    parser.add_argument("--ai-limit", type=int, default=20, help="Maximum changed files per local-AI pass (default: 20)")
    parser.add_argument("--ai-model", default="qwen3:4b-instruct", help="Installed local Ollama model to use")
    parser.add_argument("--doc-types", action="store_true",
                        help="After scanning, score the document-type axis for records under this folder")
    parser.add_argument("--doc-types-only", action="store_true",
                        help="Skip the scan; only score the document-type axis from existing registry records")
    parser.add_argument("--doc-types-force", action="store_true",
                        help="Re-score document types even where one is already recorded")
    parser.add_argument("--doc-types-limit", type=int, default=0,
                        help="Maximum records to score in this document-type pass (0 = no limit)")
    args = parser.parse_args()
    root = args.folder.resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    if args.doc_types_only:
        conn = init_db(args.db.resolve())
        stats = backfill_doc_types(conn, limit=args.doc_types_limit,
                                   force=args.doc_types_force, path_prefix=str(root))
        conn.close()
        print(f"FIS doc-type pass: considered={stats['considered']}; typed={stats['typed']}; "
              f"untyped={stats['untyped']}; missing={stats['missing']}; failed={stats['failed']}; "
              f"db={args.db.resolve()}")
        return 0

    folders, files, enriched, failed, notes, note_skips, stale, wiped = scan(
        root, args.db.resolve(), args.tree, args.write, args.html, args.local_ai,
        args.ai_limit, args.ai_model, args.file_notes, args.cleanup_stale, args.wipe_fisnotes,
    )
    mode = "wrote recursive FIS.html views and SQLite registry"
    print(
        f"FIS folder-memory.v2: {mode}; folders={folders}; direct-file records={files}; "
        f"file-notes={notes} written/{note_skips} preserved/{stale} stale removed/{wiped} pre-wiped; "
        f"local-ai={enriched} enriched/{failed} skipped; db={args.db.resolve()}"
    )
    if args.doc_types:
        conn = init_db(args.db.resolve())
        stats = backfill_doc_types(conn, limit=args.doc_types_limit,
                                   force=args.doc_types_force, path_prefix=str(root))
        conn.close()
        print(f"FIS doc-type pass: considered={stats['considered']}; typed={stats['typed']}; "
              f"untyped={stats['untyped']}; missing={stats['missing']}; failed={stats['failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
