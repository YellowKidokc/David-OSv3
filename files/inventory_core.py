#!/usr/bin/env python3
"""inventory_core.py — hash, dedupe, UID-assign every file in a folder.

Pure stdlib. Read-only on the source folder. All output goes to OUTBOX.
Designed for eventual Rust port: no magic, no frameworks, plain data in/out.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONTENT_EXTENSIONS = {
    ".md", ".html", ".htm", ".txt", ".pdf", ".docx", ".doc",
    ".tex", ".rst", ".adoc", ".org", ".rtf",
}

JUNK_NAMES = {
    "desktop.ini", "thumbs.db", ".ds_store", ".gitkeep",
}

JUNK_EXTENSIONS = {".lnk", ".tmp", ".bak", ".swp"}

# Container codes — mapped from folder_class in the profile
CONTAINER_CODES: dict[str, str] = {
    "axiom_classification_canon": "AXM",
    "canon": "CAN",
    "logos_papers": "LOG",
    "convergence": "CON",
    "genesis_to_quantum": "GTQ",
    "the_story": "STO",
    "master_equation": "MEQ",
    "boundary": "BND",
    "fruits": "FRT",
    "descent": "DSC",
    "evidence": "EVD",
    "production": "PRD",
    "glossary": "GLS",
    # fallbacks
    "independent": "IND",
    "unknown": "UNK",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    path: str
    relative_path: str
    filename: str
    extension: str
    size_bytes: int
    sha256: str
    uid: str
    modified_utc: str
    flags: list[str] = field(default_factory=list)
    duplicate_group: str | None = None


@dataclass
class InventoryResult:
    folder: str
    folder_slug: str
    container_code: str
    scanned_at: str
    total_files: int
    content_files: int
    duplicates: int
    problems: int
    files: list[FileRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Full-file SHA-256. Returns hex digest."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
    except (OSError, PermissionError):
        return "ERROR_UNREADABLE"
    return h.hexdigest()


def slugify(text: str) -> str:
    """Folder name to slug: lowercase, ascii, underscores."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)


def make_uid(container: str, sequence: int) -> str:
    """TP-{CONTAINER}-{SEQUENCE:04d}"""
    return f"TP-{container}-{sequence:04d}"


def flag_file(path: Path, size: int) -> list[str]:
    """Check a file for problems. Returns list of flag strings."""
    flags = []
    name_lower = path.name.lower()

    if size == 0:
        flags.append("EMPTY")
    if name_lower in JUNK_NAMES:
        flags.append("JUNK_NAME")
    if path.suffix.lower() in JUNK_EXTENSIONS:
        flags.append("JUNK_EXT")
    if path.name.startswith("."):
        flags.append("HIDDEN")
    if path.suffix == "" and not path.name.startswith("."):
        flags.append("NO_EXTENSION")
    if len(path.name) > 200:
        flags.append("NAME_TOO_LONG")
    # Corrupt/garbled names (mostly non-ascii control chars)
    if any(ord(c) < 32 for c in path.name):
        flags.append("CORRUPT_NAME")

    return flags


# ---------------------------------------------------------------------------
# Main inventory function
# ---------------------------------------------------------------------------

def inventory_folder(
    folder: str | Path,
    profile: dict | None = None,
    max_depth: int = 2,
) -> InventoryResult:
    """
    Walk a folder, hash every file, assign UIDs, detect duplicates.

    Args:
        folder: path to scan (read-only)
        profile: folder profile dict from 01_PROFILE (optional)
        max_depth: how deep to walk (1=root only, 2=root+one level)

    Returns:
        InventoryResult with all files, flags, and duplicate groups.
    """
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")

    # Determine container code from profile
    folder_class = (profile or {}).get("folder_class", "unknown")
    container = CONTAINER_CODES.get(folder_class, "UNK")
    folder_slug = slugify(folder.name)

    # Collect all files up to max_depth
    all_files: list[Path] = []
    for item in sorted(folder.rglob("*")):
        if not item.is_file():
            continue
        # Depth check: count parts relative to folder
        rel = item.relative_to(folder)
        if len(rel.parts) > max_depth:
            continue
        # Skip sidecars directories themselves
        if any(p.lower() in ("sidecars", "sidecars_and_json", ".git", ".venv",
                              "__pycache__", "node_modules")
               for p in rel.parts[:-1]):
            continue
        all_files.append(item)

    # Hash and record each file
    records: list[FileRecord] = []
    hash_groups: dict[str, list[int]] = defaultdict(list)
    sequence = 1

    for fpath in all_files:
        try:
            stat = fpath.stat()
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            size = -1
            modified = "ERROR"

        ext = fpath.suffix.lower()
        is_content = ext in CONTENT_EXTENSIONS
        flags = flag_file(fpath, size)

        if not is_content and ext not in JUNK_EXTENSIONS:
            flags.append("NON_CONTENT")

        file_hash = sha256_file(fpath) if size > 0 else "EMPTY"

        # UID only for content files without problems
        if is_content and not flags:
            uid = make_uid(container, sequence)
            sequence += 1
        elif is_content and flags:
            uid = make_uid(container, sequence)
            sequence += 1
        else:
            uid = ""

        rel_path = str(fpath.relative_to(folder))

        rec = FileRecord(
            path=str(fpath),
            relative_path=rel_path,
            filename=fpath.name,
            extension=ext,
            size_bytes=size,
            sha256=file_hash,
            uid=uid,
            modified_utc=modified,
            flags=flags,
        )
        records.append(rec)

        # Track hash groups for duplicate detection
        if file_hash not in ("EMPTY", "ERROR_UNREADABLE") and is_content:
            hash_groups[file_hash].append(len(records) - 1)

    # Mark duplicate groups
    dupe_group_id = 0
    total_dupes = 0
    for file_hash, indices in hash_groups.items():
        if len(indices) > 1:
            dupe_group_id += 1
            group_name = f"DG-{dupe_group_id:04d}"
            for idx in indices:
                records[idx].duplicate_group = group_name
            total_dupes += len(indices)

    content_count = sum(1 for r in records if r.extension in CONTENT_EXTENSIONS)
    problem_count = sum(1 for r in records if r.flags)

    return InventoryResult(
        folder=str(folder),
        folder_slug=folder_slug,
        container_code=container,
        scanned_at=datetime.now(timezone.utc).isoformat(),
        total_files=len(records),
        content_files=content_count,
        duplicates=total_dupes,
        problems=problem_count,
        files=records,
    )


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_inventory(result: InventoryResult, outbox: Path) -> dict[str, Path]:
    """Write inventory outputs to outbox folder. Returns paths written."""
    out_dir = outbox / result.folder_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    # Full inventory
    inv_path = out_dir / "inventory.json"
    inv_path.write_text(
        json.dumps(asdict(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["inventory"] = inv_path

    # Duplicates only
    dupes = defaultdict(list)
    for rec in result.files:
        if rec.duplicate_group:
            dupes[rec.duplicate_group].append({
                "path": rec.relative_path,
                "sha256": rec.sha256,
                "size": rec.size_bytes,
                "uid": rec.uid,
            })
    if dupes:
        dup_path = out_dir / "duplicates.json"
        dup_path.write_text(
            json.dumps(dict(dupes), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths["duplicates"] = dup_path

    # Problems only
    problems = [asdict(r) for r in result.files if r.flags]
    if problems:
        prob_path = out_dir / "problems.json"
        prob_path.write_text(
            json.dumps(problems, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths["problems"] = prob_path

    # Human-readable report
    report_lines = [
        f"# Inventory Report: {result.folder}",
        f"",
        f"Scanned: {result.scanned_at}",
        f"Container: TP-{result.container_code}",
        f"",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Total files | {result.total_files} |",
        f"| Content files | {result.content_files} |",
        f"| Duplicate files | {result.duplicates} |",
        f"| Problem files | {result.problems} |",
        f"",
    ]

    if dupes:
        report_lines.append("## Duplicates\n")
        for group, files in dupes.items():
            report_lines.append(f"### {group}\n")
            for f in files:
                report_lines.append(f"- `{f['path']}` ({f['size']:,} bytes) → {f['uid']}")
            report_lines.append("")

    if problems:
        report_lines.append("## Problems\n")
        for p in problems:
            flags = ", ".join(p["flags"])
            report_lines.append(f"- `{p['relative_path']}` — {flags}")
        report_lines.append("")

    # UID registry
    report_lines.append("## UID Registry\n")
    report_lines.append("| UID | File | Hash (first 12) |")
    report_lines.append("|---|---|---|")
    for rec in result.files:
        if rec.uid:
            h12 = rec.sha256[:12] if rec.sha256 not in ("EMPTY", "ERROR_UNREADABLE") else rec.sha256
            report_lines.append(f"| {rec.uid} | `{rec.relative_path}` | `{h12}` |")
    report_lines.append("")

    rpt_path = out_dir / "inventory_report.md"
    rpt_path.write_text("\n".join(report_lines), encoding="utf-8")
    paths["report"] = rpt_path

    return paths
