"""API endpoints for command-line jobs."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.workers.command_worker import execute_command_line

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/operator", tags=["operator"])


class CommandLineRequest(BaseModel):
    command: list[str] = Field(min_length=1)
    cwd: str | None = None
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    review_required: bool = True
    reason: str = "operator_command_line"
    metadata: dict[str, object] = Field(default_factory=dict)


def _repo() -> JobRepo:
    db = Database(DEFAULT_DB_PATH)
    return JobRepo(db.conn)


@router.post("/commands")
def create_command_line(request: CommandLineRequest) -> dict[str, object]:
    repo = _repo()
    payload = request.model_dump(exclude_none=True)
    job = repo.create_job("command_line", payload)
    if request.review_required:
        review = repo.create_review_item(job["id"], reason=request.reason, action="command_line", payload=payload)
        job = repo.update_job(job["id"], status="waiting_review", result={"review": review, "command": payload})
        return {"job": job, "review": review}
    try:
        result = execute_command_line(payload)
        repo.add_ledger_entry(job_id=job["id"], action="command_line", before=payload, after=result)
        job = repo.update_job(job["id"], status="completed", result=result)
        return {"job": job, "result": result}
    except (FileNotFoundError, PermissionError, OSError, TimeoutError, ValueError) as exc:
        job = repo.update_job(job["id"], status="failed_terminal", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
