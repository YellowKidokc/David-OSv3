"""Look (lok) — walk a tree into raw ObjectRecords. Read-only. Never mutates.

Also computes the folder tree stats (children, descendants, size, type dist).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .model import ObjectRecord, FolderRecord

# content-type by extension (coarse; refined in classify)
EXT_TYPE = {
    ".md": "markdown", ".markdown": "markdown", ".txt": "text",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".webp": "image", ".svg": "image", ".bmp": "image", ".tiff": "image",
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".avi": "video",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio",
    ".pdf": "pdf", ".docx": "document", ".doc": "document",
    ".xlsx": "spreadsheet", ".xls": "spreadsheet", ".csv": "data", ".json": "data",
    ".pptx": "presentation",
    ".zip": "archive", ".rar": "archive", ".7z": "archive", ".tar": "archive", ".gz": "archive",
    ".py": "code", ".js": "code", ".ts": "code", ".c": "code", ".cpp": "code",
    ".cs": "code", ".java": "code", ".go": "code", ".rs": "code", ".rb": "code",
    ".html": "code", ".css": "code", ".sh": "code",
    ".exe": "binary", ".dll": "binary", ".sys": "binary", ".bin": "binary", ".dat": "binary",
}


def _oid(path: str) -> str:
    return "O-" + hashlib.sha1(path.encode("utf-8", "replace")).hexdigest()[:12]


def content_type_for(name: str, is_dir: bool) -> str:
    if is_dir:
        return "folder"
    return EXT_TYPE.get(Path(name).suffix.lower(), "unknown")


def scan_tree(root: str, max_objects: int = 20000):
    """Return (objects, folders) dicts keyed by object_id.

    Skips nothing by content but is bounded by max_objects for safety on huge trees.
    """
    root = str(Path(root).resolve())
    objects: dict[str, ObjectRecord] = {}
    folders: dict[str, FolderRecord] = {}
    count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        p = Path(dirpath)
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        fid = _oid(dirpath)
        try:
            st = p.stat()
        except OSError:
            continue
        frec = FolderRecord(
            object_id=fid, name=p.name or str(p), full_path=str(p),
            rel_path="" if rel == "." else rel, depth=depth,
            direct_children=len(dirnames) + len(filenames),
        )
        folders[fid] = frec

        for fn in filenames:
            fp = p / fn
            try:
                s = fp.stat()
            except OSError:
                continue
            oid = _oid(str(fp))
            objects[oid] = ObjectRecord(
                object_id=oid, name=fn, ext=fp.suffix.lower(), full_path=str(fp),
                is_dir=False, parent=str(p), depth=depth + 1,
                rel_path=os.path.relpath(str(fp), root),
                size=s.st_size, created=s.st_ctime, modified=s.st_mtime, accessed=s.st_atime,
                content_type=content_type_for(fn, False),
            )
            frec.type_distribution[objects[oid].content_type] = \
                frec.type_distribution.get(objects[oid].content_type, 0) + 1
            frec.total_size += s.st_size
            count += 1
            if count >= max_objects:
                break
        if count >= max_objects:
            break

    _rollup(root, folders, objects)
    return objects, folders


def _rollup(root: str, folders: dict, objects: dict):
    """Fill total_descendants and empty flags by walking folder rel paths."""
    by_path = {f.full_path: f for f in folders.values()}
    # descendants = all objects+folders whose path starts with this folder path
    for f in folders.values():
        prefix = f.full_path.rstrip("\\/") + os.sep
        desc = sum(1 for o in objects.values() if o.full_path.startswith(prefix))
        desc += sum(1 for g in folders.values()
                    if g.full_path != f.full_path and g.full_path.startswith(prefix))
        f.total_descendants = desc
        f.empty = (f.direct_children == 0)
