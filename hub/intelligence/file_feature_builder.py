"""Build canonical file records: files get facts."""
from __future__ import annotations

import os
import platform
import stat
import uuid
from pathlib import Path

from hub.config.folder_profiles import FolderProfile
from hub.workers.classify_worker import classify_file
from hub.workers.hash_worker import hash_file


def build_file_record(path: str | Path, *, node_id: str = "local", folder_profile: FolderProfile | None = None) -> dict[str, object]:
    file_path = Path(path)
    normalized = str(file_path.resolve())
    stat_result = file_path.stat()
    hash_result = hash_file(str(file_path))
    classification = classify_file(str(file_path), hash_result)
    raw = _raw_facts(file_path, stat_result)
    deterministic = _deterministic_facts(classification, hash_result)
    protected = bool(folder_profile.protected) if folder_profile else False
    review_required = bool(folder_profile.review_only or folder_profile.protected) if folder_profile else True
    return {
        "identity": {
            "file_id": str(uuid.uuid5(uuid.NAMESPACE_URL, normalized)),
            "full_path": str(file_path),
            "normalized_path": normalized,
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "parent_folder_id": str(uuid.uuid5(uuid.NAMESPACE_URL, str(file_path.parent.resolve()))),
            "node_id": node_id,
            "source_machine": platform.node(),
        },
        "raw": raw,
        "deterministic": deterministic,
        "ai_advised": {
            "tags": [], "domain": None, "context": None, "role": None, "confidence": 0.0,
            "evidence_json": [], "provenance": "not_run",
        },
        "provenance": {
            "raw_fields": {key: "filesystem" for key in raw},
            "deterministic_fields": {key: "deterministic_worker" for key in deterministic},
            "ai_advised_fields": "empty_until_ai_advisor_runs",
        },
        "operational": {
            "current_status": "indexed", "last_health_check": None, "last_worker_touched": "file_feature_builder",
            "attempts": 1, "error_text": None,
        },
        "policy": {
            "protected_flag": protected,
            "review_required": review_required,
            "allowed_actions_json": ["suggest_rename", "summarize", "route_suggestion"],
            "blocked_actions_json": ["delete"],
            "naming_policy": (folder_profile.routing_hints.get("naming_policy") if folder_profile else None),
            "routing_candidates_json": [],
        },
        "relationships": {
            "project_id": None, "group_id": None, "series_id": None,
            "related_files_json": [], "sidecar_links_json": [], "folder_summary_weight": 1.0,
        },
    }


def _raw_facts(path: Path, stat_result: os.stat_result) -> dict[str, object]:
    mode = stat_result.st_mode
    return {
        "size": stat_result.st_size,
        "created_at": stat_result.st_ctime,
        "modified_at": stat_result.st_mtime,
        "accessed_at": stat_result.st_atime,
        "hidden": path.name.startswith("."),
        "system": False,
        "read_only": not bool(mode & stat.S_IWUSR),
        "owner": _owner(stat_result),
    }


def _deterministic_facts(classification: dict[str, object], hash_result: dict[str, object]) -> dict[str, object]:
    metadata = dict(classification.get("metadata") or {})
    return {
        "mime_type": classification.get("mime_type"),
        "magic_type": classification.get("reason"),
        "kind": classification.get("kind") or classification.get("category"),
        "parser_used": classification.get("parser"),
        "parse_status": "parsed" if classification.get("parser") != "none" else "not_applicable",
        "language": _language_from_name(str(classification.get("path", ""))),
        "structure_metrics": _structure_metrics(metadata),
        "fast_hash": hash_result.get("digest", "")[:16],
        "full_hash": hash_result.get("digest"),
        "content_fingerprint": hash_result.get("digest"),
        "duplicate_group_id": hash_result.get("digest"),
        "near_duplicate_score": None,
        "extracted_metadata": metadata,
        "excerpt": None,
        "first_heading_or_first_line": None,
    }


def _structure_metrics(metadata: dict[str, object]) -> dict[str, object]:
    keys = {"page_count", "sheet_count", "sample_rows", "sample_columns", "duration", "width", "height", "paragraph_count"}
    return {key: value for key, value in metadata.items() if key in keys}


def _language_from_name(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    return {".py": "python", ".js": "javascript", ".ts": "typescript", ".sql": "sql", ".html": "html"}.get(suffix)


def _owner(stat_result: os.stat_result) -> str | None:
    if hasattr(os, "getuid") and stat_result.st_uid == os.getuid():
        return str(stat_result.st_uid)
    return str(getattr(stat_result, "st_uid", "")) or None
