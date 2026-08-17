"""API action registry endpoints for React, AHK, and bridge clients."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from hub.services.api_action_registry import (
    ApiActionRegistryError,
    get_api_action,
    list_api_actions,
)

DEFAULT_ACTIONS_PATH = Path(os.environ.get("FIHUB_API_ACTIONS_PATH", "config/top_of_mind/api_actions.example.json"))
router = APIRouter(prefix="/api-actions", tags=["api-actions"])


@router.get("")
def list_actions(group: str | None = None) -> dict[str, object]:
    try:
        return list_api_actions(DEFAULT_ACTIONS_PATH, group=group)
    except ApiActionRegistryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{action_id}")
def get_action(action_id: str) -> dict[str, object]:
    try:
        return {"action": get_api_action(action_id, DEFAULT_ACTIONS_PATH)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApiActionRegistryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
