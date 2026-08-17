"""Static app catalog and serving routes."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/apps", tags=["apps"])

DEFAULT_APPS_ROOT = Path(os.environ.get("FIHUB_APPS_ROOT", r"D:\GitHub\David-OS\apps"))
APP_ID_RE = re.compile(r"^[A-Za-z0-9_. -]+$")


def _apps_root() -> Path:
    return DEFAULT_APPS_ROOT.resolve()


def _app_source(app_dir: Path) -> Path:
    dist = app_dir / "dist"
    if (dist / "index.html").is_file():
        return dist
    return app_dir


def _app_dir(app_id: str) -> Path:
    if not APP_ID_RE.match(app_id):
        raise HTTPException(status_code=404, detail="app not found")
    root = _apps_root()
    candidate = (root / app_id).resolve()
    if root not in candidate.parents or not candidate.is_dir():
        raise HTTPException(status_code=404, detail="app not found")
    return candidate


def _safe_file(base: Path, rel_path: str) -> Path:
    target = (base / rel_path).resolve()
    if base not in target.parents and target != base:
        raise HTTPException(status_code=404, detail="file not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return target


@router.get("")
def list_apps() -> dict[str, object]:
    root = _apps_root()
    apps: list[dict[str, object]] = []
    if not root.is_dir():
        return {"apps_root": str(root), "apps": apps}

    for app_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        source = _app_source(app_dir)
        index = source / "index.html"
        html_files = sorted(p.name for p in source.glob("*.html"))
        apps.append(
            {
                "id": app_dir.name,
                "path": str(app_dir),
                "served_from": str(source),
                "url": f"/apps/{app_dir.name}",
                "has_index": index.is_file(),
                "html_files": html_files[:25],
            }
        )
    return {"apps_root": str(root), "apps": apps}


@router.get("/{app_id}")
def serve_app_index(app_id: str) -> FileResponse:
    source = _app_source(_app_dir(app_id))
    index = source / "index.html"
    if index.is_file():
        return FileResponse(index)
    html_files = sorted(source.glob("*.html"))
    if html_files:
        return FileResponse(html_files[0])
    raise HTTPException(status_code=404, detail="app has no index or html file")


@router.get("/{app_id}/{rel_path:path}")
def serve_app_file(app_id: str, rel_path: str) -> FileResponse:
    source = _app_source(_app_dir(app_id))
    target = _safe_file(source, rel_path)
    return FileResponse(target)
