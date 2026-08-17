"""SQLite-backed cache for fast desktop-tier file lookup."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> object:
    return json.loads(value)


def _normalize(path: str | Path) -> str:
    return str(Path(path)).replace("\\", "/").lower()


class DesktopFileCacheRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_file(
        self,
        *,
        full_path: str,
        tier: str = "desktop",
        owner_id: str = "shared",
        size_bytes: int = 0,
        modified_at: str | None = None,
        created_at_fs: str | None = None,
        tags: list[str] | None = None,
        metadata: JsonDict | None = None,
    ) -> JsonDict:
        path = Path(full_path)
        normalized_path = _normalize(path)
        self.conn.execute(
            """
            INSERT INTO desktop_file_cache (
                normalized_path, full_path, filename, extension, parent_path, tier, owner_id,
                size_bytes, modified_at, created_at_fs, tags_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_path) DO UPDATE SET
                full_path = excluded.full_path,
                filename = excluded.filename,
                extension = excluded.extension,
                parent_path = excluded.parent_path,
                tier = excluded.tier,
                owner_id = excluded.owner_id,
                size_bytes = excluded.size_bytes,
                modified_at = excluded.modified_at,
                created_at_fs = excluded.created_at_fs,
                tags_json = excluded.tags_json,
                metadata_json = excluded.metadata_json,
                last_seen_at = datetime('now')
            """,
            (
                normalized_path,
                str(path),
                path.name,
                path.suffix.lower(),
                str(path.parent),
                tier,
                owner_id,
                int(size_bytes),
                modified_at,
                created_at_fs,
                _dump(tags or []),
                _dump(metadata or {}),
            ),
        )
        self.conn.commit()
        return self.get_by_path(full_path)

    def get_by_path(self, full_path: str) -> JsonDict:
        row = self.conn.execute(
            "SELECT * FROM desktop_file_cache WHERE normalized_path = ?",
            (_normalize(full_path),),
        ).fetchone()
        if row is None:
            raise KeyError(f"cached file not found: {full_path}")
        return self._file(row)

    def search(
        self,
        query: str,
        *,
        tier: str | None = None,
        owner_id: str | None = None,
        extension: str | None = None,
        limit: int = 75,
    ) -> list[JsonDict]:
        clauses = ["(filename LIKE ? OR full_path LIKE ? OR tags_json LIKE ?)"]
        pattern = f"%{query}%"
        params: list[object] = [pattern, pattern, pattern]
        if tier:
            clauses.append("tier = ?")
            params.append(tier)
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if extension:
            clauses.append("extension = ?")
            params.append(extension if extension.startswith(".") else f".{extension}")
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(
            f"""
            SELECT * FROM desktop_file_cache
            WHERE {' AND '.join(clauses)}
            ORDER BY last_seen_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._file(row) for row in rows]

    def list_recent(self, *, tier: str | None = None, owner_id: str | None = None, limit: int = 75) -> list[JsonDict]:
        clauses: list[str] = []
        params: list[object] = []
        if tier:
            clauses.append("tier = ?")
            params.append(tier)
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(
            f"SELECT * FROM desktop_file_cache{where} ORDER BY last_seen_at DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._file(row) for row in rows]

    @staticmethod
    def _file(row: sqlite3.Row) -> JsonDict:
        return {
            "id": row["id"],
            "full_path": row["full_path"],
            "filename": row["filename"],
            "extension": row["extension"],
            "parent_path": row["parent_path"],
            "tier": row["tier"],
            "owner_id": row["owner_id"],
            "size_bytes": row["size_bytes"],
            "modified_at": row["modified_at"],
            "created_at_fs": row["created_at_fs"],
            "tags": _load(row["tags_json"]),
            "metadata": _load(row["metadata_json"]),
            "last_seen_at": row["last_seen_at"],
            "indexed_at": row["indexed_at"],
        }
