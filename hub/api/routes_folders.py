"""Folder registry endpoints for Top of Mind."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hub.storage.db import Database
from hub.storage.folder_repo import FolderRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/folders", tags=["folders"])


class FolderRequest(BaseModel):
    name: str
    folder_code: int | None = None
    parent_id: int | None = None
    wall: str = "main"
    wall_code: int = 50001
    owner_id: str = "shared"
    visibility: str = "shared"
    sort_order: int = 100
    metadata: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=3)


class FolderArchiveRequest(BaseModel):
    archived: bool = True


def _repo() -> FolderRepo:
    db = Database(DEFAULT_DB_PATH)
    return FolderRepo(db.conn)


@router.post("")
def create_folder(request: FolderRequest) -> dict[str, object]:
    try:
        return {"folder": _repo().create_folder(**request.model_dump())}
    except (sqlite3.IntegrityError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_folders(
    wall: str | None = None,
    parent_id: int | None = None,
    owner_id: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
) -> dict[str, object]:
    return {
        "folders": _repo().list_folders(
            wall=wall,
            parent_id=parent_id,
            owner_id=owner_id,
            tag=tag,
            include_archived=include_archived,
        )
    }


@router.get("/search")
def search_folders(
    q: str,
    wall: str | None = None,
    owner_id: str | None = None,
    include_archived: bool = False,
) -> dict[str, object]:
    return {"folders": _repo().search_folders(q, wall=wall, owner_id=owner_id, include_archived=include_archived)}


@router.get("/tree")
def folder_tree(
    wall: str | None = None,
    owner_id: str | None = None,
    include_archived: bool = False,
) -> dict[str, object]:
    return {"folders": _repo().folder_tree(wall=wall, owner_id=owner_id, include_archived=include_archived)}


@router.get("/{folder_id}")
def get_folder(folder_id: int) -> dict[str, object]:
    try:
        return {"folder": _repo().get_folder(folder_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{folder_id}/archive")
def archive_folder(folder_id: int, request: FolderArchiveRequest) -> dict[str, object]:
    try:
        return {"folder": _repo().archive_folder(folder_id, archived=request.archived)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
