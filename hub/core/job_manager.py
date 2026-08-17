"""Hub brain for the first file-event-to-review vertical slice."""
from __future__ import annotations

from pathlib import Path

from hub.config.folder_profiles import FolderProfileRegistry
from hub.core.review_gate import ReviewGate
from hub.storage.job_repo import JobRepo
from hub.watchers.event_normalizer import normalize_file_event
from hub.workers.classify_worker import classify_file
from hub.workers.hash_worker import hash_file
from hub.workers.rename_worker import execute_rename, suggest_rename


class JobManager:
    def __init__(self, repo: JobRepo, profiles: FolderProfileRegistry | None = None) -> None:
        self.repo = repo
        self.profiles = profiles or FolderProfileRegistry()
        self.review_gate = ReviewGate(repo)

    def ingest_file_event(self, raw_event: dict[str, object], *, source: str = "watcher") -> dict[str, object]:
        event = normalize_file_event(raw_event, source=source)
        profile = self.profiles.match(event.get("dest_path") or event["path"])
        job = self.repo.create_job("file_event", {"event": event, "folder_profile": profile.to_payload()})
        return self.process_file_event(job["id"])

    def process_file_event(self, job_id: int) -> dict[str, object]:
        job = self.repo.get_job(job_id)
        event = job["payload"]["event"]
        profile = self.profiles.match(event.get("dest_path") or event["path"])
        path = event.get("dest_path") if event["event_type"] == "moved" and event.get("dest_path") else event["path"]
        if event["event_type"] == "deleted" or event.get("is_directory"):
            return self.repo.update_job(job_id, status="ignored", result={"reason": "not_a_rename_candidate", "event": event})
        self.repo.update_job(job_id, status="running")
        if not Path(path).is_file():
            return self.repo.update_job(job_id, status="failed_retryable", error=f"file not found: {path}")

        hash_result = hash_file(path)
        classification = classify_file(path, hash_result)
        suggestion = suggest_rename(path, classification, hash_result)
        gate = self.review_gate.evaluate_rename(job_id, suggestion, folder_profile=profile)
        result = {
            "event": event,
            "folder_profile": profile.to_payload(),
            "hash": hash_result,
            "classification": classification,
            "rename_suggestion": suggestion,
            "review_gate": gate,
        }

        if gate["requires_review"]:
            return self.repo.update_job(job_id, status="waiting_review", result=result)

        rename_result = execute_rename(suggestion)
        self.repo.add_ledger_entry(job_id=job_id, action="rename", before={"path": path}, after=rename_result)
        result["rename_result"] = rename_result
        return self.repo.update_job(job_id, status="completed", result=result)
