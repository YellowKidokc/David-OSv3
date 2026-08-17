"""Node heartbeat, health, and safe repair endpoints."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from hub.services.node_health import NodeHealthService
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.storage.node_repo import NodeRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/nodes", tags=["nodes"])


class NodeHeartbeatRequest(BaseModel):
    node_id: str
    hostname: str = ""
    role: str = "peer"
    capabilities: list[str] = Field(default_factory=list)
    status: str = "isolated_but_running"
    priority: int = Field(default=100, ge=0)
    hub_url: str | None = None
    leader_status: Literal["primary", "backup", "helper"] = "helper"
    is_primary: bool = False
    resources: dict[str, object] = Field(default_factory=dict)
    local_queue_depth: int = 0
    version: str = "unknown"
    build_signature: str = "unknown"


class PeerHeartbeatRequest(NodeHeartbeatRequest):
    node_role: str | None = None


class RepairRequest(BaseModel):
    artifact_path: str
    source_root: str
    source_node: str | None = None


def _service(node_id: str = "local") -> NodeHealthService:
    db = Database(DEFAULT_DB_PATH)
    return NodeHealthService(NodeRepo(db.conn), JobRepo(db.conn), node_id=node_id)


@router.post("/heartbeat")
def local_heartbeat(request: NodeHeartbeatRequest | None = Body(default=None), node_id: str = "local") -> dict[str, object]:
    if request is not None:
        return {"node": _service().receive_peer_heartbeat(request.model_dump())}
    return {"node": _service(node_id).heartbeat()}


@router.post("/peer-heartbeat")
def peer_heartbeat(request: PeerHeartbeatRequest) -> dict[str, object]:
    return {"node": _service().receive_peer_heartbeat(request.model_dump())}


@router.get("/health")
def local_health(node_id: str = "local") -> dict[str, object]:
    return {"health": _service(node_id).check_local_health()}


@router.get("")
def list_nodes() -> dict[str, object]:
    db = Database(DEFAULT_DB_PATH)
    return {"nodes": NodeRepo(db.conn).list_nodes()}


@router.get("/status")
def node_status() -> dict[str, object]:
    db = Database(DEFAULT_DB_PATH)
    nodes = NodeRepo(db.conn).list_node_status()
    primary = next((node for node in nodes if node["is_primary"] or node["leader_status"] == "primary"), None)
    return {"primary": primary, "nodes": nodes}


@router.get("/capabilities")
def list_capabilities() -> dict[str, object]:
    db = Database(DEFAULT_DB_PATH)
    return {"capabilities": NodeRepo(db.conn).list_capabilities()}


@router.get("/capabilities/{capability}/nodes")
def nodes_for_capability(capability: str) -> dict[str, object]:
    db = Database(DEFAULT_DB_PATH)
    return {"capability": capability, "nodes": NodeRepo(db.conn).nodes_for_capability(capability)}


@router.post("/repair/safe-artifact")
def repair_safe_artifact(request: RepairRequest) -> dict[str, object]:
    try:
        return {"repair": _service().repair_safe_artifact(request.artifact_path, source_root=request.source_root, source_node=request.source_node)}
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
