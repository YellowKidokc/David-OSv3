"""Top of Mind API for multi-agent messages, folders, walls, and controls."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.top_of_mind_repo import TopOfMindRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/top-of-mind", tags=["top-of-mind"])


class SourceRequest(BaseModel):
    source_id: str
    label: str
    kind: str = "ai"
    priority: int = Field(default=5, ge=0, le=10)
    status: str = "active"
    muted: bool = False
    paused: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class SourceStateRequest(BaseModel):
    status: str | None = None
    muted: bool | None = None
    paused: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10)


class MessageRequest(BaseModel):
    source_id: str
    body: str
    source_label: str | None = None
    source_code: int | None = None
    type_code: int = 30001
    role: str = "assistant"
    priority: int | None = Field(default=None, ge=0, le=10)
    priority_code: int = 40003
    wall: str = "main"
    wall_code: int = 50001
    folder: str = "Main"
    folder_code: int = 60001
    pinned: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class MessageStateRequest(BaseModel):
    pinned: bool | None = None
    archived: bool | None = None
    wall: str | None = None
    folder: str | None = None


class CombineRequest(BaseModel):
    message_ids: list[int]
    wall: str = "main"
    folder: str = "Main"


def _repo() -> TopOfMindRepo:
    db = Database(DEFAULT_DB_PATH)
    return TopOfMindRepo(db.conn)


@router.post("/sources")
def upsert_source(request: SourceRequest) -> dict[str, object]:
    return {"source": _repo().upsert_source(**request.model_dump())}


@router.get("/sources")
def list_sources() -> dict[str, object]:
    return {"sources": _repo().list_sources()}


@router.patch("/sources/{source_id}")
def set_source_state(source_id: str, request: SourceStateRequest) -> dict[str, object]:
    try:
        return {"source": _repo().set_source_state(source_id, **request.model_dump())}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/messages")
def post_message(request: MessageRequest) -> dict[str, object]:
    return {"message": _repo().post_message(**request.model_dump())}


@router.get("/messages")
def list_messages(
    source_id: str | None = None,
    wall: str | None = None,
    folder: str | None = None,
    pinned: bool | None = None,
    include_archived: bool = False,
    limit: int = 75,
) -> dict[str, object]:
    return {
        "messages": _repo().list_messages(
            source_id=source_id,
            wall=wall,
            folder=folder,
            pinned=pinned,
            include_archived=include_archived,
            limit=limit,
        )
    }


@router.patch("/messages/{message_id}")
def set_message_state(message_id: int, request: MessageStateRequest) -> dict[str, object]:
    try:
        return {"message": _repo().set_message_state(message_id, **request.model_dump())}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/combine")
def combine_messages(request: CombineRequest) -> dict[str, object]:
    try:
        return {"message": _repo().combine_messages(request.message_ids, wall=request.wall, folder=request.folder)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/controls/end-all")
def end_all_sources() -> dict[str, object]:
    return {"sources": _repo().stop_all_sources()}
