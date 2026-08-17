"""API endpoints for explicit file actions requested by folder agents or bridge tools."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.workers.file_action_worker import execute_file_action

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/operator", tags=["operator"])

FileAction = Literal["write_text", "append_text", "touch", "copy", "move", "archive", "delete", "open"]


class FileActionRequest(BaseModel):
    action: FileAction
    source_path: str | None = None
    target_path: str | None = None
    text: str | None = None
    encoding: str = "utf-8"
    create_parent_dirs: bool = True
    overwrite: bool = False
    review_required: bool = True
    reason: str = "operator_file_action"
    metadata: dict[str, object] = Field(default_factory=dict)


def _repo() -> JobRepo:
    db = Database(DEFAULT_DB_PATH)
    return JobRepo(db.conn)


@router.post("/file-actions")
def create_file_action(request: FileActionRequest) -> dict[str, object]:
    repo = _repo()
    payload = request.model_dump(exclude_none=True)
    job = repo.create_job("file_action", payload)
    if request.review_required:
        review = repo.create_review_item(job["id"], reason=request.reason, action="file_action", payload=payload)
        job = repo.update_job(job["id"], status="waiting_review", result={"review": review, "action": payload})
        return {"job": job, "review": review}
    try:
        result = execute_file_action(payload)
        repo.add_ledger_entry(job_id=job["id"], action=f"file_action:{request.action}", before=payload, after=result)
        job = repo.update_job(job["id"], status="completed", result=result)
        return {"job": job, "result": result}
    except (FileNotFoundError, FileExistsError, PermissionError, OSError, ValueError) as exc:
        job = repo.update_job(job["id"], status="failed_terminal", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
