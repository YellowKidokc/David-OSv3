"""Semantic addressing API routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from hub.services.semantic_addressing import score_semantic_address

router = APIRouter(prefix="/semantic", tags=["semantic"])


class SemanticScoreRequest(BaseModel):
    path: str | None = Field(default=None, description="File path to score.")
    text: str | None = Field(default=None, description="Optional pre-extracted text to score.")

    @model_validator(mode="after")
    def require_path_or_text(self) -> "SemanticScoreRequest":
        if not self.path and not self.text:
            raise ValueError("Either path or text is required.")
        return self


@router.post("/score")
def score_semantic(request: SemanticScoreRequest) -> dict[str, object]:
    target_path = request.path or "inline-text.txt"
    try:
        result = score_semantic_address(Path(target_path), text=request.text)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"semantic_address": result}
