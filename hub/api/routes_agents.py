"""Agent routing: send an outbound message addressed to a specific agent.

The hub records the message in the shared Top of Mind stream with a
`target_agent_id` and `delivery: pending` marker. A client (AHK bridge, desk)
polls for pending outbound messages and delivers them to the target AI, then
the reply comes back in through /top-of-mind/messages.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.top_of_mind_repo import TopOfMindRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/agents", tags=["agents"])


class AgentSendRequest(BaseModel):
    agent_id: str | None = None
    body: str | None = None
    target: str | dict[str, object] | None = None
    message: str | None = None
    action: str | None = None
    route_only: bool = False
    dry_run: bool = False
    from_id: str = "operator"
    from_label: str = "Operator"
    role: str = "user"          # message is FROM the operator/hub TO the agent
    wall: str = "main"
    folder: str = "Outbound"
    priority: int | None = Field(default=None, ge=0, le=10)
    metadata: dict[str, object] = Field(default_factory=dict)


def _repo() -> TopOfMindRepo:
    db = Database(DEFAULT_DB_PATH)
    return TopOfMindRepo(db.conn)


@router.get("/list")
def list_agents() -> dict[str, object]:
    """Agents are Top of Mind sources; this mirrors /top-of-mind/sources."""
    return {"agents": _repo().list_sources()}


@router.post("/send")
def agent_send(request: AgentSendRequest) -> dict[str, object]:
    agent_id = request.agent_id
    if not agent_id and isinstance(request.target, str):
        agent_id = request.target
    if not agent_id and isinstance(request.target, dict):
        agent_id = str(request.target.get("id") or request.target.get("source_id") or request.target.get("name") or "unknown")
    body = request.body or request.message
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id or target is required")
    if not body:
        raise HTTPException(status_code=422, detail="body or message is required")

    metadata = dict(request.metadata)
    metadata.update(
        {
            "target_agent_id": agent_id,
            "delivery": "pending",
            "action": request.action or "agent_send",
            "route_only": request.route_only,
            "dry_run": request.dry_run,
        }
    )
    try:
        message = _repo().post_message(
            source_id=request.from_id,
            source_label=request.from_label,
            body=body,
            role=request.role,
            wall=request.wall,
            folder=request.folder,
            priority=request.priority,
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001 - surface storage errors as 400
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": message, "target_agent_id": agent_id, "delivery": "pending"}
