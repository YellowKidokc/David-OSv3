"""Tiered folder summary strategy: folders get patterns."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SummaryStrategy:
    mode: str
    sample_size: int
    scan_depth: int
    confidence: float


def choose_summary_strategy(file_count: int) -> SummaryStrategy:
    if file_count <= 25:
        return SummaryStrategy("near_full", file_count, 10, 0.95)
    if file_count <= 200:
        return SummaryStrategy("aggregate_plus_representative_sample", 25, 6, 0.86)
    if file_count <= 2_000:
        return SummaryStrategy("aggregate_first_semantic_sample_second", 40, 4, 0.76)
    if file_count <= 10_000:
        return SummaryStrategy("compressed_overview", 50, 2, 0.64)
    return SummaryStrategy("territory", 75, 1, 0.55)


def summarize_file_records(folder_path: str | Path, records: list[dict[str, object]], *, folder_profile: dict[str, object], review_queue_count: int = 0) -> dict[str, object]:
    folder = Path(folder_path).resolve()
    strategy = choose_summary_strategy(len(records))
    extension_distribution = Counter(str(record["identity"]["extension"]) or "<none>" for record in records)
    kind_distribution = Counter(str(record["deterministic"].get("kind") or "unknown") for record in records)
    total_size = sum(int(record["raw"].get("size", 0)) for record in records)
    duplicate_groups = Counter(str(record["deterministic"].get("duplicate_group_id")) for record in records)
    duplicate_pressure = sum(count - 1 for count in duplicate_groups.values() if count > 1)
    metadata_missing = sum(1 for record in records if not record["deterministic"].get("extracted_metadata"))
    action_pressure = _action_pressure(records, duplicate_pressure, metadata_missing, review_queue_count)
    modified_times = [float(record["raw"].get("modified_at", 0)) for record in records if record["raw"].get("modified_at")]
    summary = {
        "folder_identity": {"folder_path": str(folder), "folder_role": folder_profile.get("folder_role", "general")},
        "file_count": len(records),
        "subfolder_count": len([path for path in folder.iterdir() if path.is_dir()]) if folder.exists() else 0,
        "total_size": total_size,
        "extension_distribution": dict(extension_distribution.most_common()),
        "kind_distribution": dict(kind_distribution.most_common()),
        "dominant_tags": [],
        "dominant_domain": None,
        "dominant_time_range": {"min_modified": min(modified_times) if modified_times else None, "max_modified": max(modified_times) if modified_times else None},
        "health_score": _health_score(records, duplicate_pressure, review_queue_count),
        "symptom_count": duplicate_pressure + review_queue_count + metadata_missing,
        "duplicate_pressure": duplicate_pressure,
        "review_queue_count": review_queue_count,
        "churn_rate": _churn_rate(modified_times),
        "summary_mode": strategy.mode,
        "summary_confidence": strategy.confidence,
        "sample_size": strategy.sample_size,
        "scan_depth": strategy.scan_depth,
        "top_risk_drivers": _top_risk_drivers(duplicate_pressure, review_queue_count, metadata_missing),
    }
    return {
        "folder_id": _folder_id(folder),
        "folder_path": str(folder),
        "folder_profile": folder_profile,
        "summary": summary,
        "provenance": {"summary_source": "deterministic_only", "sample_size": strategy.sample_size, "strategy": strategy.mode, "ai_enriched": False},
        "action_pressure": action_pressure,
        "last_summary_version": 1,
    }


def _action_pressure(records: list[dict[str, object]], duplicate_pressure: int, metadata_missing: int, review_queue_count: int) -> dict[str, object]:
    rename_pressure = sum(1 for record in records if " " in str(record["identity"]["filename"]))
    pressures = {
        "rename_cleanup": rename_pressure,
        "duplicate_cleanup": duplicate_pressure,
        "archive_pressure": sum(1 for record in records if record["deterministic"].get("kind") == "archive"),
        "routing_pressure": sum(1 for record in records if record["policy"].get("routing_candidates_json") == []),
        "metadata_fill_pressure": metadata_missing,
        "manual_review_pressure": review_queue_count,
    }
    dominant = max(pressures, key=pressures.get) if pressures else "none"
    return {"dominant": dominant, "scores": pressures}


def _health_score(records: list[dict[str, object]], duplicate_pressure: int, review_queue_count: int) -> float:
    if not records:
        return 1.0
    penalty = min(0.7, (duplicate_pressure + review_queue_count) / max(len(records), 1))
    return round(1.0 - penalty, 3)


def _churn_rate(modified_times: list[float]) -> float:
    if len(modified_times) < 2:
        return 0.0
    return round((max(modified_times) - min(modified_times)) / max(len(modified_times), 1), 3)


def _top_risk_drivers(duplicate_pressure: int, review_queue_count: int, metadata_missing: int) -> list[str]:
    drivers = []
    if duplicate_pressure:
        drivers.append("duplicates")
    if review_queue_count:
        drivers.append("manual_review_queue")
    if metadata_missing:
        drivers.append("missing_metadata")
    return drivers


def _folder_id(folder: Path) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(folder)))
