"""Read APIs for file records and folder summaries."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from hub.storage.db import Database
from hub.storage.intelligence_repo import IntelligenceRepo

DEFAULT_DB_PATH = Path(os.environ.get("FIHUB_DB_PATH", ".data/file-intelligence-hub.sqlite3"))
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _repo() -> IntelligenceRepo:
    db = Database(DEFAULT_DB_PATH)
    return IntelligenceRepo(db.conn)


@router.get("/files")
def list_file_records(folder_path: str) -> dict[str, object]:
    return {"file_records": _repo().list_file_records_under(str(Path(folder_path).resolve()))}


@router.get("/folders/summary")
def get_folder_summary(folder_path: str) -> dict[str, object]:
    try:
        return {"folder_summary": _repo().get_folder_summary(str(Path(folder_path).resolve()))}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
