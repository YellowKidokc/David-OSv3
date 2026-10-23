"""Observe-only Master Equation corpus intake analysis.

The analyzer preserves every file location while grouping identical content by
SHA-256.  It writes only to the requested output directory; source files are
never renamed, moved, deleted, sidecarred, or rewritten.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from engine.fingerprint import sha256_file
from engine.text_extractor import extract_text


SKIP_DIRS = {".git", ".obsidian", ".fis", "__pycache__", "node_modules", ".lake"}
SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}

VARIABLE_TERMS = {
    "G": ("grace", "gravity", "newton-grace"),
    "M": ("moral alignment", "momentum", "newton-momentum"),
    "E": ("truth signal", "maxwell", "electromagnet", "maxwell-truth"),
    "S_eff": ("entropy", "clausius", "judgment"),
    "T": ("kairos", "temporal", "phase transition"),
    "K": ("logos", "shannon", "information channel"),
    "R": ("relational frame", "reference frame", "covenant"),
    "Q": ("quantum uncertainty", "heisenberg", "superposition"),
    "F": ("fruit of the spirit", "fruits of the spirit", "yukawa", "strong force"),
    "C_W": ("coherence", "christ", "decoherence"),
}

SEMANTIC_TERMS = {
    "master-equation": ("master equation", "master_equation", "master-eq"),
    "derivation": ("derivation", "derive", "lagrangian", "noether"),
    "canon": ("canonical", "canon", "source of truth"),
    "proof": ("proof", "theorem", "lemma", "lean"),
    "bridge": ("bridge", "isomorphism", "structural correspondence"),
    "consciousness": ("consciousness", "sentience", "observer"),
    "trinity": ("trinity", "triune", "father son spirit"),
    "evidence": ("evidence", "experiment", "prediction", "falsif"),
}

ADULT_TERMS = (
    "onlyfans", "sextape", "blowjob", "pussy", "masturbat", "porn", "xxx",
    "brattysis", "blowketing", "dick", "doggystyle", "4some",
)
INSTALLER_TERMS = ("installer", "setup.exe")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def _io_path(path: Path) -> str:
    """Return a Windows extended-length path while retaining normal display paths."""
    value = str(path.resolve())
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return "\\\\?\\" + value
    return value


def _iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        for name in filenames:
            if name.lower() in SKIP_NAMES or name.endswith(".fmeta"):
                continue
            yield Path(dirpath) / name


def _source_lane(relative: Path) -> str:
    parts = [p.lower() for p in relative.parts]
    joined = "/".join(parts)
    if any("archive" in p or p == "zzz_archive" for p in parts):
        return "archive"
    if any("intake" in p or p == "inbox" for p in parts):
        return "intake"
    if "canon" in joined:
        return "canon"
    if "derivation" in joined:
        return "derivation"
    if "laws" in parts or "law" in parts:
        return "laws"
    if "intro" in parts:
        return "introduction"
    if "blue" in joined:
        return "blue"
    if "inputs" in parts:
        return "inputs"
    return "root_or_other"


def _role(relative: Path, text: str) -> str:
    blob = (relative.as_posix() + " " + text[:20_000]).lower()
    if relative.suffix.lower() in {".py", ".js", ".ts", ".lean", ".ps1", ".bat", ".ahk"}:
        return "code_or_formal"
    if "receipt" in blob or "manifest" in blob or "ledger" in blob:
        return "receipt_or_ledger"
    if "derivation" in blob or "lagrangian" in blob:
        return "derivation"
    if "canon" in blob:
        return "canon_candidate"
    if "evidence" in blob or "audit" in blob or "prediction" in blob:
        return "evidence_or_audit"
    if relative.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".mp3", ".m4a", ".mp4", ".wav"}:
        return "media"
    if relative.suffix.lower() in {".zip", ".7z", ".tar", ".gz"}:
        return "archive_bundle"
    return "document_or_support"


def _matches(blob: str, table: dict[str, tuple[str, ...]]) -> list[str]:
    return [label for label, terms in table.items() if any(term in blob for term in terms)]


def _contamination_flags(path: Path) -> list[str]:
    name = path.name.lower()
    flags = []
    if any(term in name for term in ADULT_TERMS):
        flags.append("explicit_adult_filename")
    if path.suffix.lower() == ".exe" or any(term in name for term in INSTALLER_TERMS):
        flags.append("executable_or_installer")
    return flags


def analyze(root: Path, output: Path) -> dict:
    root = root.resolve()
    output = output.resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    if output == root or root in output.parents:
        raise ValueError("Output must be outside the source corpus")
    output.mkdir(parents=True, exist_ok=True)

    records = []
    errors = []
    for path in sorted(_iter_files(root), key=lambda p: str(p).lower()):
        try:
            relative = path.relative_to(root)
            stat = os.stat(_io_path(path))
            text = extract_text(_io_path(path), limit=200_000)
            searchable = (relative.as_posix() + " " + text).lower()
            digest = sha256_file(_io_path(path))
            flags = _contamination_flags(path)
            records.append({
                "instance_id": _stable_id("INS", str(path.resolve()).lower()),
                "content_id": f"OBJ-{digest[:16]}",
                "source_path": str(path),
                "relative_path": relative.as_posix(),
                "name": path.name,
                "extension": path.suffix.lower(),
                "bytes": stat.st_size,
                "sha256": digest,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(timespec="seconds"),
                "source_lane": _source_lane(relative),
                "role": _role(relative, text),
                "semantic_tags": _matches(searchable, SEMANTIC_TERMS),
                "meq_variables": _matches(searchable, VARIABLE_TERMS),
                "contamination_flags": flags,
                "review_status": "NEEDS_REVIEW" if flags else "UNRESOLVED",
                "text_chars_sampled": len(text),
            })
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})

    by_hash = defaultdict(list)
    for record in records:
        by_hash[record["sha256"]].append(record)
    duplicate_groups = [group for group in by_hash.values() if len(group) > 1]

    _write_sqlite(output / "master_equation_intake.sqlite", records, by_hash)
    _write_files_csv(output / "all_file_instances.csv", records)
    _write_duplicates_csv(output / "exact_duplicate_groups.csv", duplicate_groups)
    _write_errors_csv(output / "scan_errors.csv", errors)

    summary = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_root": str(root),
        "output_root": str(output),
        "mode": "observe_only_no_source_mutation",
        "file_instances": len(records),
        "unique_content_objects": len(by_hash),
        "exact_duplicate_groups": len(duplicate_groups),
        "duplicate_instances": sum(len(group) for group in duplicate_groups),
        "extra_duplicate_locations": sum(len(group) - 1 for group in duplicate_groups),
        "scan_errors": len(errors),
        "source_lanes": dict(Counter(r["source_lane"] for r in records)),
        "roles": dict(Counter(r["role"] for r in records)),
        "variable_coverage": {key: sum(key in r["meq_variables"] for r in records) for key in VARIABLE_TERMS},
        "semantic_coverage": {key: sum(key in r["semantic_tags"] for r in records) for key in SEMANTIC_TERMS},
        "contamination_flagged": sum(bool(r["contamination_flags"]) for r in records),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_start_here(output / "START_HERE_MASTER_EQUATION_INTAKE.md", summary, records, duplicate_groups)
    return summary


def _write_sqlite(path: Path, records: list[dict], by_hash: dict[str, list[dict]]) -> None:
    con = sqlite3.connect(path)
    try:
        con.executescript("""
        DROP TABLE IF EXISTS file_instances;
        DROP TABLE IF EXISTS content_objects;
        CREATE TABLE content_objects(
          content_id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, bytes INTEGER,
          instance_count INTEGER NOT NULL
        );
        CREATE TABLE file_instances(
          instance_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, source_path TEXT UNIQUE NOT NULL,
          relative_path TEXT, name TEXT, extension TEXT, bytes INTEGER, modified_at TEXT,
          source_lane TEXT, role TEXT, semantic_tags_json TEXT, meq_variables_json TEXT,
          contamination_flags_json TEXT, review_status TEXT, text_chars_sampled INTEGER,
          FOREIGN KEY(content_id) REFERENCES content_objects(content_id)
        );
        CREATE INDEX idx_instances_content ON file_instances(content_id);
        CREATE INDEX idx_instances_lane ON file_instances(source_lane);
        CREATE INDEX idx_instances_role ON file_instances(role);
        """)
        for digest, group in by_hash.items():
            con.execute("INSERT INTO content_objects VALUES (?,?,?,?)",
                        (group[0]["content_id"], digest, group[0]["bytes"], len(group)))
        for r in records:
            con.execute("INSERT INTO file_instances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                r["instance_id"], r["content_id"], r["source_path"], r["relative_path"], r["name"],
                r["extension"], r["bytes"], r["modified_at"], r["source_lane"], r["role"],
                json.dumps(r["semantic_tags"]), json.dumps(r["meq_variables"]),
                json.dumps(r["contamination_flags"]), r["review_status"], r["text_chars_sampled"],
            ))
        con.commit()
    finally:
        con.close()


def _write_files_csv(path: Path, records: list[dict]) -> None:
    fields = ["instance_id", "content_id", "source_path", "relative_path", "name", "extension",
              "bytes", "sha256", "modified_at", "source_lane", "role", "semantic_tags",
              "meq_variables", "contamination_flags", "review_status", "text_chars_sampled"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("semantic_tags", "meq_variables", "contamination_flags"):
                row[key] = "|".join(row[key])
            writer.writerow(row)


def _write_duplicates_csv(path: Path, groups: list[list[dict]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["content_id", "sha256", "instance_count", "source_lane", "relative_path", "source_path"])
        for group in sorted(groups, key=lambda g: (-len(g), g[0]["sha256"])):
            for record in group:
                writer.writerow([record["content_id"], record["sha256"], len(group),
                                 record["source_lane"], record["relative_path"], record["source_path"]])


def _write_errors_csv(path: Path, errors: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "error"])
        writer.writeheader()
        writer.writerows(errors)


def _write_start_here(path: Path, summary: dict, records: list[dict], groups: list[list[dict]]) -> None:
    lines = [
        "# Master Equation Intake — START HERE", "",
        f"Source: `{summary['source_root']}`", "",
        "Mode: **observe only**. No source file was moved, renamed, deleted, shortened, or rewritten.", "",
        "## Corpus shape", "",
        f"- File instances: {summary['file_instances']:,}",
        f"- Unique content objects: {summary['unique_content_objects']:,}",
        f"- Exact duplicate groups: {summary['exact_duplicate_groups']:,}",
        f"- Extra duplicate locations retained: {summary['extra_duplicate_locations']:,}",
        f"- Scan errors: {summary['scan_errors']:,}",
        f"- Conservative contamination flags: {summary['contamination_flagged']:,}", "",
        "## Source lanes", "",
    ]
    lines.extend(f"- {key}: {value:,}" for key, value in sorted(summary["source_lanes"].items()))
    lines += ["", "## Document roles", ""]
    lines.extend(f"- {key}: {value:,}" for key, value in sorted(summary["roles"].items()))
    lines += ["", "## Ten-variable coverage", ""]
    lines.extend(f"- {key}: {value:,} files" for key, value in summary["variable_coverage"].items())
    lines += ["", "## Largest exact-duplicate families", ""]
    for group in sorted(groups, key=lambda g: (-len(g), g[0]["sha256"]))[:20]:
        lines.append(f"### {group[0]['content_id']} — {len(group)} locations")
        lines.extend(f"- `{r['relative_path']}` ({r['source_lane']})" for r in group)
        lines.append("")
    flagged = [r for r in records if r["contamination_flags"]]
    lines += ["## Conservative contamination review", ""]
    if not flagged:
        lines.append("No filename-level contamination indicators were detected.")
    else:
        for r in flagged:
            lines.append(f"- `{r['relative_path']}` — {', '.join(r['contamination_flags'])}")
    lines += ["", "## Outputs", "",
              "- `master_equation_intake.sqlite`: content objects plus every file instance",
              "- `all_file_instances.csv`: complete review ledger",
              "- `exact_duplicate_groups.csv`: duplicate families without deletion proposals",
              "- `scan_errors.csv`: unresolved read failures",
              "- `summary.json`: machine-readable corpus summary", "",
              "Nothing in this report is canon admission. All statuses remain unresolved until human review."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
