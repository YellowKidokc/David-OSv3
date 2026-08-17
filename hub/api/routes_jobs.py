"""Small FastAPI router for job intake and review decisions."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.core.job_manager import JobManager
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.workers.review_worker import apply_approved_review

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(tags=["control-plane"])


class FileEventRequest(BaseModel):
    event_type: str = Field(default="created")
    path: str
    is_directory: bool = False
    dest_path: str | None = None
    source: str = "api"


class ReviewDecisionRequest(BaseModel):
    status: Literal["approved", "rejected", "deferred"]


class FolderSummaryRequest(BaseModel):
    folder_path: str


class HelpRequest(BaseModel):
    requested_capability: str
    source_node_id: str
    file_path: str | None = None
    folder_path: str | None = None
    reason: str
    payload: dict[str, object] = Field(default_factory=dict)
    status: str = "queued"
    priority: int = Field(default=90, ge=0)


def _repo() -> JobRepo:
    db = Database(DEFAULT_DB_PATH)
    return JobRepo(db.conn)


@router.post("/jobs/file-events")
def create_file_event(request: FileEventRequest) -> dict[str, object]:
    repo = _repo()
    manager = JobManager(repo)
    return manager.ingest_file_event(request.model_dump(exclude={"source"}, exclude_none=True), source=request.source)


@router.post("/jobs/folder-summaries")
def create_folder_summary_job(request: FolderSummaryRequest) -> dict[str, object]:
    return _repo().create_job("folder_summary", {"folder_path": request.folder_path})


@router.post("/jobs/help-requests")
def create_help_request(request: HelpRequest) -> dict[str, object]:
    if not request.file_path and not request.folder_path:
        raise HTTPException(status_code=400, detail="file_path or folder_path is required")
    if request.status != "queued":
        raise HTTPException(status_code=400, detail="help_request jobs must be created with status='queued'")
    payload = request.model_dump()
    payload["status"] = "queued"
    return {"job": _repo().create_job("help_request", payload, priority=request.priority)}


@router.get("/jobs")
def list_jobs(status: str | None = None) -> dict[str, object]:
    return {"jobs": _repo().list_jobs(status=status)}


@router.get("/jobs/stats")
def job_stats() -> dict[str, object]:
    return {"stats": _repo().job_stats()}


@router.get("/jobs/{job_id}/events")
def list_job_events(job_id: int) -> dict[str, object]:
    try:
        _repo().get_job(job_id)
        return {"events": _repo().list_job_events(job_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/reviews")
def list_reviews(
    status: str | None = None,
    action: str | None = None,
    folder_role: str | None = None,
    older_than_hours: float | None = None,
) -> dict[str, object]:
    return {
        "review_items": _repo().list_review_items(
            status=status, action=action, folder_role=folder_role, older_than_hours=older_than_hours
        )
    }


@router.get("/reviews/{review_id}")
def get_review(review_id: int) -> dict[str, object]:
    try:
        return {"review_item": _repo().get_review_item(review_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reviews/{review_id}/decision")
def decide_review(review_id: int, request: ReviewDecisionRequest) -> dict[str, object]:
    repo = _repo()
    try:
        review = repo.decide_review_item(review_id, request.status)
        if request.status == "approved":
            result = apply_approved_review(repo, review_id)
        elif request.status == "deferred":
            result = repo.update_job(review["job_id"], status="deferred", result={"review": review})
        else:
            result = {"review": review}
        return {"review": review, "result": result}
    except (KeyError, ValueError, FileNotFoundError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reviews/{review_id}/approve")
def approve_review(review_id: int) -> dict[str, object]:
    return decide_review(review_id, ReviewDecisionRequest(status="approved"))


@router.post("/reviews/{review_id}/reject")
def reject_review(review_id: int) -> dict[str, object]:
    return decide_review(review_id, ReviewDecisionRequest(status="rejected"))


@router.post("/reviews/{review_id}/defer")
def defer_review(review_id: int) -> dict[str, object]:
    return decide_review(review_id, ReviewDecisionRequest(status="deferred"))


@router.post("/jobs/{job_id}/requeue")
def requeue_job(job_id: int) -> dict[str, object]:
    try:
        return {"job": _repo().requeue_job(job_id)}
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
