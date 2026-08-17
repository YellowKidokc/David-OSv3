"""Prediction endpoints for file-action suggestions."""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from hub.intelligence.prediction_engine import default_prediction_engine

router = APIRouter(prefix="/predict", tags=["prediction-engine"])


class ObserveRequest(BaseModel):
    action: str
    file_path: str
    destination: str | None = None
    old_name: str | None = None
    new_name: str | None = None
    chi_dominant: str = ""
    chi_hash: str = ""


class PredictRequest(BaseModel):
    file_path: str
    action: str = "move"


class CorrectRequest(BaseModel):
    prediction_id: str
    actual_destination: str | None = None
    actual_name: str | None = None


class PermanentRuleRequest(BaseModel):
    prediction_id: str
    rule_type: str = "extension"
    pattern: str | None = None


@router.post("/observe")
def observe(req: ObserveRequest) -> dict[str, object]:
    engine = default_prediction_engine()
    engine.observe(
        action=req.action,
        file_path=req.file_path,
        destination=req.destination,
        old_name=req.old_name,
        new_name=req.new_name,
        chi_dominant=req.chi_dominant,
        chi_hash=req.chi_hash,
    )
    return {"status": "observed", "total_observations": engine.db.total_observations()}


@router.post("/predict")
def predict(req: PredictRequest) -> dict[str, object]:
    return default_prediction_engine().predict(file_path=req.file_path, action=req.action).to_dict()


@router.post("/correct")
def correct(req: CorrectRequest) -> dict[str, object]:
    default_prediction_engine().correct(
        req.prediction_id,
        actual_destination=req.actual_destination,
        actual_name=req.actual_name,
    )
    return {"status": "corrected"}


@router.post("/make-permanent")
def make_permanent(req: PermanentRuleRequest) -> dict[str, object]:
    result = default_prediction_engine().make_permanent(
        req.prediction_id,
        rule_type=req.rule_type,
        pattern=req.pattern,
    )
    if not result:
        raise HTTPException(status_code=404, detail="prediction not found")
    return result


@router.get("/stats")
def stats() -> dict[str, object]:
    return default_prediction_engine().stats()


@router.get("/rules")
def rules() -> dict[str, object]:
    return {"rules": default_prediction_engine().db.rules()}
