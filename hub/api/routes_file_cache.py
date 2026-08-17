"""API routes for desktop-tier file cache lookup."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.desktop_file_cache_repo import DesktopFileCacheRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/files/cache", tags=["file-cache"])


class CachedFileRequest(BaseModel):
    full_path: str
    tier: str = "desktop"
    owner_id: str = "shared"
    size_bytes: int = 0
    modified_at: str | None = None
    created_at_fs: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


def _repo() -> DesktopFileCacheRepo:
    db = Database(DEFAULT_DB_PATH)
    return DesktopFileCacheRepo(db.conn)


@router.post("")
def upsert_cached_file(request: CachedFileRequest) -> dict[str, object]:
    return {"file": _repo().upsert_file(**request.model_dump())}


@router.get("")
def list_cached_files(tier: str | None = None, owner_id: str | None = None, limit: int = 75) -> dict[str, object]:
    return {"files": _repo().list_recent(tier=tier, owner_id=owner_id, limit=limit)}


@router.get("/search")
def search_cached_files(
    q: str,
    tier: str | None = None,
    owner_id: str | None = None,
    extension: str | None = None,
    limit: int = 75,
) -> dict[str, object]:
    return {"files": _repo().search(q, tier=tier, owner_id=owner_id, extension=extension, limit=limit)}


@router.get("/by-path")
def get_cached_file(path: str) -> dict[str, object]:
    try:
        return {"file": _repo().get_by_path(path)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
