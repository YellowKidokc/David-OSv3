"""FIS report and local structured Q&A routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.services.report_builder import (
    answer_report_question,
    build_report,
    get_report,
    record_feedback,
)

router = APIRouter(prefix="/fis", tags=["fis"])


class ReportRequest(BaseModel):
    scan: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    duration: str | float | int | None = None


class AskRequest(BaseModel):
    report_id: str
    question: str


class FeedbackRequest(BaseModel):
    report_id: str
    suggestion_id: str
    rating: int = Field(ge=1, le=5)
    accepted: bool | None = None


@router.post("/report")
def create_fis_report(req: ReportRequest) -> dict[str, Any]:
    return build_report(req.scan, source=req.source, duration=req.duration)


@router.post("/ask")
def ask_fis_report(req: AskRequest) -> dict[str, str]:
    report = get_report(req.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    return answer_report_question(report, req.question)


@router.post("/feedback")
def feedback(req: FeedbackRequest) -> dict[str, Any]:
    try:
        return record_feedback(req.report_id, req.suggestion_id, req.rating, req.accepted)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc.args[0]}") from exc
