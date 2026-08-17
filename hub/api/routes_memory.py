"""Memory and future vector-search API."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.memory_repo import MemoryRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryItemRequest(BaseModel):
    title: str
    body: str
    source: str = "api"
    folder: str = "Memory"
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    embedding: list[float] | None = None


def _repo() -> MemoryRepo:
    db = Database(DEFAULT_DB_PATH)
    return MemoryRepo(db.conn)


@router.post("/items")
def create_memory_item(request: MemoryItemRequest) -> dict[str, object]:
    return {"memory_item": _repo().create_item(**request.model_dump())}


@router.get("/items")
def list_memory_items(folder: str | None = None, source: str | None = None, limit: int = 75) -> dict[str, object]:
    return {"memory_items": _repo().list_items(folder=folder, source=source, limit=limit)}


@router.get("/items/{item_id}")
def get_memory_item(item_id: int) -> dict[str, object]:
    try:
        return {"memory_item": _repo().get_item(item_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/search")
def search_memory(q: str, limit: int = 25, mode: str = "text") -> dict[str, object]:
    repo = _repo()
    if mode == "vector":
        return {"memory_items": repo.vector_search(q, limit=limit)}
    return {"memory_items": repo.search(q, limit=limit)}


@router.post("/embed-pending")
def embed_pending_memory(limit: int = 100) -> dict[str, object]:
    return {"memory_items": _repo().embed_pending(limit=limit)}
