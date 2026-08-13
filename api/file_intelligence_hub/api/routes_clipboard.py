"""Clipboard shelf API: durable clipboard history, pins, folders, tags.

AutoHotkey is the watcher/hand and POSTs entries here; SQLite is the memory.
The React desk and AI agents read/search through these endpoints instead of
touching the raw Windows clipboard.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from file_intelligence_hub.storage.clipboard_repo import ClipboardRepo
from file_intelligence_hub.storage.db import Database

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/clipboard", tags=["clipboard"])


class ClipboardItemRequest(BaseModel):
    body: str
    kind: str = "text"
    source_app: str | None = None
    source_window: str | None = None
    folder: str | None = None
    tags: str | None = None
    pinned: bool = False


class ClipboardItemStateRequest(BaseModel):
    body: str | None = None
    folder: str | None = None
    tags: str | None = None
    pinned: bool | None = None
    deleted: bool | None = None


class ClipboardImportRequest(BaseModel):
    items: list[dict[str, object]] = Field(default_factory=list)


def _repo() -> ClipboardRepo:
    db = Database(DEFAULT_DB_PATH)
    return ClipboardRepo(db.conn)


@router.post("/items")
def save_item(request: ClipboardItemRequest) -> dict[str, object]:
    return {"item": _repo().save_item(**request.model_dump())}


@router.post("/save")
def save_item_alias(request: ClipboardItemRequest) -> dict[str, object]:
    """Friendly alias for bridge clients that speak in clipboard actions."""
    return save_item(request)


@router.get("/items")
def list_items(
    folder: str | None = None,
    pinned: bool | None = None,
    query: str | None = None,
    include_deleted: bool = False,
    limit: int = 100,
) -> dict[str, object]:
    return {
        "items": _repo().list_items(
            folder=folder,
            pinned=pinned,
            query=query,
            include_deleted=include_deleted,
            limit=limit,
        )
    }


@router.patch("/items/{item_id}")
def set_item_state(item_id: int, request: ClipboardItemStateRequest) -> dict[str, object]:
    try:
        return {"item": _repo().set_item_state(item_id, **request.model_dump())}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/items/{item_id}")
def delete_item(item_id: int) -> dict[str, object]:
    try:
        return {"item": _repo().soft_delete(item_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/items/{item_id}/copy")
def copy_item(item_id: int) -> dict[str, object]:
    """Stamp usage and hand the body back so AHK can put it on the clipboard."""
    try:
        return {"item": _repo().mark_copied(item_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/export")
def export_items(include_deleted: bool = False) -> dict[str, object]:
    return {"items": _repo().list_items(include_deleted=include_deleted, limit=100000)}


@router.post("/import")
def import_items(request: ClipboardImportRequest) -> dict[str, object]:
    return {"stored": _repo().import_items(request.items)}
