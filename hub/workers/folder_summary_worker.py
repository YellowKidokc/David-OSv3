"""Folder summary worker: folders get patterns, large folders get rollups."""
from __future__ import annotations

from pathlib import Path

from hub.config.folder_profiles import FolderProfileRegistry
from hub.intelligence.file_feature_builder import build_file_record
from hub.intelligence.folder_feature_builder import summarize_file_records
from hub.storage.intelligence_repo import IntelligenceRepo
from hub.storage.job_repo import JobRepo
from hub.workers.asset_pair_worker import detect_asset_pairs


class FolderSummaryWorker:
    def __init__(self, intelligence_repo: IntelligenceRepo, job_repo: JobRepo, profiles: FolderProfileRegistry | None = None) -> None:
        self.intelligence_repo = intelligence_repo
        self.job_repo = job_repo
        self.profiles = profiles or FolderProfileRegistry()

    def summarize_folder(self, folder_path: str | Path, *, node_id: str = "local") -> dict[str, object]:
        folder = Path(folder_path)
        profile = self.profiles.match(folder)
        records = []
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                record = build_file_record(path, node_id=node_id, folder_profile=profile)
                records.append(self.intelligence_repo.upsert_file_record(record))
        self._attach_sidecar_links(records)
        review_count = len(self.job_repo.list_review_items(status="pending", folder_role=profile.folder_role))
        summary = summarize_file_records(folder, records, folder_profile=profile.to_payload(), review_queue_count=review_count)
        return self.intelligence_repo.upsert_folder_summary(summary)

    def _attach_sidecar_links(self, records: list[dict[str, object]]) -> None:
        pairs = detect_asset_pairs([str(record["identity"]["normalized_path"]) for record in records])
        if not pairs:
            return
        for record in records:
            normalized = str(record["identity"]["normalized_path"])
            if normalized not in pairs:
                continue
            record["relationships"]["sidecar_links_json"] = pairs[normalized]
            self.intelligence_repo.upsert_file_record(record)
