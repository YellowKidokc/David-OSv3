"""Observe/propose-only topic closure planner.

Find topic candidates in selected roots, group exact content with SHA-256, and
propose one keeper. This module never copies, moves, or deletes source files.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from engine.fingerprint import sha256_file
from engine.text_extractor import extract_text

SKIP_DIRS = {".git", ".obsidian", ".fis", "__pycache__", "node_modules", ".lake", "$recycle.bin", "system volume information"}
SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store", "pagefile.sys", "hiberfil.sys", "swapfile.sys"}
TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".html", ".htm", ".json", ".yaml", ".yml", ".csv", ".tex", ".lean", ".py", ".ps1", ".docx", ".pdf"}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "term-closure"


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def _io_path(path: Path) -> str:
    value = str(path.resolve())
    return "\\\\?\\" + value if os.name == "nt" and not value.startswith("\\\\?\\") else value


def _iter_files(roots: list[Path]):
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _exc: None):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
            for name in filenames:
                if name.lower() not in SKIP_NAMES and not name.endswith(".fmeta"):
                    yield root, Path(dirpath) / name


def _hits(blob: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term.lower() in blob]


def _tier(name_hits: int, body_hits: int, canon: bool, support: bool) -> tuple[str, list[str]]:
    reasons = (["topic_in_name_or_path"] if name_hits else []) + (["topic_in_content"] if body_hits else [])
    reasons += (["canon_or_approved_signal"] if canon else []) + (["evidence_or_derivation_signal"] if support else [])
    if canon and (name_hits or body_hits >= 2): return "GOLD_1", reasons
    if name_hits and body_hits: return "GOLD_2", reasons
    if body_hits >= 2 or support: return "GOLD_3", reasons
    if name_hits or body_hits: return "GOLD_4", reasons
    return "UNRESOLVED", reasons


def _keeper_key(record: dict) -> tuple:
    order = {"GOLD_1": 0, "GOLD_2": 1, "GOLD_3": 2, "GOLD_4": 3, "UNRESOLVED": 4}
    path = record["source_path"].lower()
    return (order[record["quality_tier"]], 0 if any(x in path for x in ("canon", "approved", "production")) else 1,
            1 if any(x in path for x in ("archive", "backup", "copy")) else 0, len(path), path)


def plan_closure(roots: list[Path], output: Path, topic: str, terms: list[str] | None = None) -> dict:
    roots = [r.resolve() for r in roots]
    missing = [str(r) for r in roots if not r.is_dir()]
    if missing: raise ValueError(f"Not directories: {', '.join(missing)}")
    output = output.resolve()
    if any(output == root or root in output.parents for root in roots):
        raise ValueError("Output must be outside every scanned source root")
    terms = list(dict.fromkeys([topic, *(terms or [])]))
    output.mkdir(parents=True, exist_ok=True)
    project_root = Path.home() / "Documents" / "David-OS Closures" / slugify(topic)
    records, errors = [], []
    for root, path in _iter_files(roots):
        try:
            relative = path.relative_to(root); path_blob = relative.as_posix().lower()
            name_hits = _hits(path_blob, terms)
            text = extract_text(_io_path(path), limit=200_000) if path.suffix.lower() in TEXT_EXTENSIONS else ""
            body_hits = _hits(text.lower(), terms)
            if not name_hits and not body_hits: continue
            context = f"{path_blob} {text[:50000].lower()}"
            canon = any(x in context for x in ("canonical", "canon", "approved", "source of truth"))
            support = any(x in context for x in ("derivation", "evidence", "proof", "audit", "receipt", "manifest"))
            tier, reasons = _tier(len(name_hits), len(body_hits), canon, support)
            stat = os.stat(_io_path(path)); digest = sha256_file(_io_path(path))
            records.append({"instance_id": _stable_id("INS", str(path).lower()), "content_id": f"OBJ-{digest[:16]}",
                "sha256": digest, "source_root": str(root), "source_path": str(path), "relative_path": relative.as_posix(),
                "name": path.name, "bytes": stat.st_size, "quality_tier": tier,
                "tier_status": "PROPOSED_NOT_ADJUDICATED", "reasons": reasons,
                "matched_terms": sorted(set(name_hits + body_hits))})
        except Exception as exc: errors.append({"path": str(path), "error": str(exc)})
    by_hash = defaultdict(list)
    for record in records: by_hash[record["sha256"]].append(record)
    for group in by_hash.values():
        keeper = min(group, key=_keeper_key)
        for record in group:
            is_keeper = record is keeper
            record.update({"proposed_keeper": is_keeper, "keeper_instance_id": keeper["instance_id"],
                "proposed_target": str(project_root / "KEEPERS" / record["quality_tier"] / keeper["name"]) if is_keeper else "",
                "duplicate_pointer_target": "" if is_keeper else str(project_root / "DUPLICATE_POINTERS" / f"{record['instance_id']}.json"),
                "deletion_eligibility": "KEEP" if is_keeper else "NOT_ELIGIBLE_UNTIL_KEEPER_COPIED_HASH_VERIFIED_AND_HUMAN_APPROVED"})
    fields = ["instance_id", "content_id", "sha256", "source_root", "source_path", "relative_path", "name", "bytes", "quality_tier", "tier_status", "reasons", "matched_terms", "proposed_keeper", "keeper_instance_id", "proposed_target", "duplicate_pointer_target", "deletion_eligibility"]
    with (output / "closure_plan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for record in records:
            row = dict(record); row["reasons"] = "|".join(row["reasons"]); row["matched_terms"] = "|".join(row["matched_terms"]); writer.writerow(row)
    (output / "closure_plan.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "scan_errors.json").write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mode": "observe_and_propose_only_no_source_mutation", "topic": topic, "terms": terms,
        "source_roots": [str(r) for r in roots], "proposed_project_root": str(project_root),
        "candidate_instances": len(records), "unique_content_objects": len(by_hash),
        "duplicate_groups": sum(len(g) > 1 for g in by_hash.values()),
        "extra_duplicate_locations": sum(max(0, len(g) - 1) for g in by_hash.values()),
        "quality_tiers": dict(Counter(r["quality_tier"] for r in records)), "scan_errors": len(errors),
        "safety_gate": "Keeper copied and SHA-256 verified, exact paths human-approved, quarantine, then receipt."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "START_HERE_TERM_CLOSURE.md").write_text(
        f"# {topic} closure plan\n\n**Observe/propose only.** No source file was copied, moved, or deleted.\n\n"
        f"Candidates: {len(records)}; unique objects: {len(by_hash)}; duplicate groups: {summary['duplicate_groups']}.\n\n"
        "GOLD_1 through GOLD_4 are quality/relevance proposals, not epistemic L1-L4 and not canon decisions. "
        "Duplicate pointers represent original locations without making more copies. Deletion stays locked until a keeper is copied, hash-verified, human-approved, quarantined, and receipted.\n",
        encoding="utf-8")
    return summary
