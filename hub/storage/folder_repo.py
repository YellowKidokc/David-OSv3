"""Persistence for Top of Mind folders and nested folder trees."""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

JsonDict = dict[str, Any]
SLUG_RE = re.compile(r"[^a-z0-9]+")
CUSTOM_FOLDER_CODE_START = 60020


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> object:
    return json.loads(value)


def _slug(name: str) -> str:
    slug = SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "folder"


def _normalize_tags(tags: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for tag in tags or []:
        cleaned = tag.strip().lower()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    if len(normalized) > 3:
        raise ValueError("folders support up to three tags")
    return normalized


class FolderRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create_folder(
        self,
        *,
        name: str,
        folder_code: int | None = None,
        parent_id: int | None = None,
        wall: str = "main",
        wall_code: int = 50001,
        owner_id: str = "shared",
        visibility: str = "shared",
        sort_order: int = 100,
        metadata: JsonDict | None = None,
        tags: list[str] | None = None,
    ) -> JsonDict:
        code = folder_code or self.next_folder_code()
        normalized_tags = _normalize_tags(tags)
        cur = self.conn.execute(
            """
            INSERT INTO top_folders (
                folder_code, name, slug, parent_id, wall, wall_code, owner_id, visibility, sort_order, metadata_json, tags_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, name, _slug(name), parent_id, wall, wall_code, owner_id, visibility, sort_order, _dump(metadata or {}), _dump(normalized_tags)),
        )
        self.conn.commit()
        return self.get_folder(int(cur.lastrowid))

    def next_folder_code(self) -> int:
        row = self.conn.execute(
            "SELECT MAX(folder_code) AS max_code FROM top_folders WHERE folder_code >= ?",
            (CUSTOM_FOLDER_CODE_START,),
        ).fetchone()
        max_code = row["max_code"] if row and row["max_code"] is not None else CUSTOM_FOLDER_CODE_START - 1
        return int(max_code) + 1

    def get_folder(self, folder_id: int) -> JsonDict:
        row = self.conn.execute("SELECT * FROM top_folders WHERE id = ?", (folder_id,)).fetchone()
        if row is None:
            raise KeyError(f"folder not found: {folder_id}")
        return self._folder(row)

    def list_folders(
        self,
        *,
        wall: str | None = None,
        parent_id: int | None = None,
        owner_id: str | None = None,
        tag: str | None = None,
        include_archived: bool = False,
    ) -> list[JsonDict]:
        clauses: list[str] = []
        params: list[object] = []
        if wall:
            clauses.append("wall = ?")
            params.append(wall)
        if parent_id is not None:
            clauses.append("parent_id = ?")
            params.append(parent_id)
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if tag:
            clauses.append("tags_json LIKE ?")
            params.append(f'%"{tag.strip().lower()}"%')
        if not include_archived:
            clauses.append("archived = 0")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(f"SELECT * FROM top_folders{where} ORDER BY sort_order ASC, name ASC", params).fetchall()
        return [self._folder(row) for row in rows]

    def search_folders(
        self,
        query: str,
        *,
        owner_id: str | None = None,
        wall: str | None = None,
        include_archived: bool = False,
    ) -> list[JsonDict]:
        needle = f"%{query.lower()}%"
        clauses = ["(lower(name) LIKE ? OR lower(slug) LIKE ? OR lower(metadata_json) LIKE ? OR lower(tags_json) LIKE ?)"]
        params: list[object] = [needle, needle, needle, needle]
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if wall:
            clauses.append("wall = ?")
            params.append(wall)
        if not include_archived:
            clauses.append("archived = 0")
        rows = self.conn.execute(
            f"SELECT * FROM top_folders WHERE {' AND '.join(clauses)} ORDER BY sort_order ASC, name ASC", params
        ).fetchall()
        return [self._folder(row) for row in rows]

    def folder_tree(self, *, owner_id: str | None = None, wall: str | None = None, include_archived: bool = False) -> list[JsonDict]:
        folders = self.list_folders(owner_id=owner_id, wall=wall, include_archived=include_archived)
        by_id = {folder["id"]: {**folder, "children": []} for folder in folders}
        roots: list[JsonDict] = []
        for folder in by_id.values():
            parent_id = folder["parent_id"]
            if parent_id in by_id:
                by_id[parent_id]["children"].append(folder)
            else:
                roots.append(folder)
        return roots

    def archive_folder(self, folder_id: int, *, archived: bool = True) -> JsonDict:
        self.get_folder(folder_id)
        self.conn.execute("UPDATE top_folders SET archived = ? WHERE id = ?", (int(archived), folder_id))
        self.conn.commit()
        return self.get_folder(folder_id)

    @staticmethod
    def _folder(row: sqlite3.Row) -> JsonDict:
        return {
            "id": row["id"],
            "folder_code": row["folder_code"],
            "name": row["name"],
            "slug": row["slug"],
            "parent_id": row["parent_id"],
            "wall": row["wall"],
            "wall_code": row["wall_code"],
            "owner_id": row["owner_id"],
            "visibility": row["visibility"],
            "sort_order": row["sort_order"],
            "metadata": _load(row["metadata_json"]),
            "tags": _load(row["tags_json"]) if "tags_json" in row.keys() else [],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
