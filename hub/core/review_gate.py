"""Review gate for risky or low-confidence actions."""
from __future__ import annotations

from hub.config.folder_profiles import FolderProfile
from hub.rules.thresholds import rename_requires_review
from hub.storage.job_repo import JobRepo


class ReviewGate:
    def __init__(self, repo: JobRepo) -> None:
        self.repo = repo

    def evaluate_rename(
        self,
        job_id: int,
        suggestion: dict[str, object],
        *,
        folder_profile: FolderProfile | None = None,
    ) -> dict[str, object]:
        requires_review, reason = rename_requires_review(suggestion, folder_profile=folder_profile)
        decision = {"requires_review": requires_review, "reason": reason, "suggestion": suggestion}
        if requires_review:
            review = self.repo.create_review_item(job_id, reason=reason, action="rename", payload=suggestion)
            decision["review_item"] = review
        return decision
