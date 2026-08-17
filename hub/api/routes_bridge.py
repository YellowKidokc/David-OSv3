"""Desktop AHK overlay bridge proxy endpoints."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from typing import Literal

from pydantic import BaseModel, Field


BRIDGE_URL = os.environ.get("DAVID_OS_AHK_BRIDGE_URL", "http://localhost:8765")
BRIDGE_TOKEN = os.environ.get("DAVID_OS_AHK_BRIDGE_TOKEN", "davidos-bridge-2026")
BridgeTarget = Literal["claude", "codex", "gpt", "kimi"]

router = APIRouter(prefix="/bridge", tags=["desktop-bridge"])


class BridgeSendRequest(BaseModel):
    text: str = Field(min_length=1)
    target: BridgeTarget = "codex"
    enters: int = Field(default=0, ge=0, le=5)
    dry_run: bool = False


class BridgeJobRequest(BaseModel):
    worker: str = "ahk-main"
    action: str = Field(min_length=1)
    target: str | dict[str, object] | None = "codex"
    payload: dict[str, object] = Field(default_factory=dict)
    source: str = "desk"
    dry_run: bool = False


def _target_id(target: str | dict[str, object] | None) -> BridgeTarget:
    if isinstance(target, dict):
        raw = str(target.get("id") or target.get("source_id") or target.get("name") or "codex")
    else:
        raw = str(target or "codex")
    raw = raw.lower()
    if raw in {"claude", "codex", "gpt", "kimi"}:
        return raw  # type: ignore[return-value]
    return "codex"


def _payload_text(payload: dict[str, object]) -> str:
    for key in ("text", "message", "body", "content"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _bridge_request(path: str, method: str = "GET", payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None
    headers = {"X-Bridge-Token": BRIDGE_TOKEN}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{BRIDGE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"AHK bridge unavailable at {BRIDGE_URL}: {exc}") from exc


@router.get("/health")
def bridge_health() -> dict[str, object]:
    return {"bridge": _bridge_request("/health")}


@router.post("/send")
def bridge_send(request: BridgeSendRequest) -> dict[str, object]:
    payload = request.model_dump()
    return {"bridge": _bridge_request("/send", method="POST", payload=payload), "payload": payload}


@router.get("/jobs")
def bridge_jobs(worker: str = "ahk-main") -> dict[str, object]:
    """Compatibility endpoint for desks that poll bridge jobs.

    The current local bridge is direct/proxy based (`/bridge/send`), so this
    returns an empty queue unless a future durable job store is added.
    """
    return {"worker": worker, "jobs": []}


@router.post("/jobs")
def create_bridge_job(request: BridgeJobRequest) -> dict[str, object]:
    """Accept the desk's bridge-job shape and proxy safe send-like actions.

    Dry-run requests are acknowledged without touching the desktop bridge.
    When the AHK listener is offline, the route returns 503 with a clear
    message from `_bridge_request`.
    """
    target = _target_id(request.target)
    text = _payload_text(request.payload)
    dry_run = request.dry_run or bool(request.payload.get("dry_run"))
    job = {
        "id": f"bridge-{request.worker}-{request.action}",
        "worker": request.worker,
        "action": request.action,
        "target": target,
        "payload": request.payload,
        "source": request.source,
        "status": "dry_run" if dry_run else "accepted",
    }
    if dry_run:
        return {"job": job, "delivery": "dry_run"}
    if request.action in {"send_to_active", "paste_to_active", "push_clipboard", "agent_send"} and text:
        bridge_payload = {"text": text, "target": target, "enters": 1 if request.action == "send_to_active" else 0, "dry_run": False}
        return {"job": job, "bridge": _bridge_request("/send", method="POST", payload=bridge_payload)}
    return {"job": job, "delivery": "queued_placeholder"}
