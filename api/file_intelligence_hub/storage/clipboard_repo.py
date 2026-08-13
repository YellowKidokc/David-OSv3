"""Persistence for the clipboard shelf.

AutoHotkey watches the Windows clipboard and POSTs entries here; the hub is the
durable memory. Clients never open this database directly -- only the server writes.
"""
from __future__ import annotations

import sqlite3
from typing import Any

JsonDict = dict[str, Any]


class ClipboardRepo:
    """Store the clipboard history: quick saves, pins, folders, tags, soft deletes."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def save_item(
        self,
        *,
        body: str,
        kind: str = "text",
        source_app: str | None = None,
        source_window: str | None = None,
        folder: str | None = None,
        tags: str | None = None,
        pinned: bool = False,
    ) -> JsonDict:
        cursor = self.conn.execute(
            """
            INSERT INTO clipboard_items (body, kind, source_app, source_window, folder, tags, pinned)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (body, kind, source_app, source_window, folder, tags, int(pinned)),
        )
        self.conn.commit()
        return self.get_item(int(cursor.lastrowid))

    def get_item(self, item_id: int) -> JsonDict:
        row = self.conn.execute(
            "SELECT * FROM clipboard_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"clipboard item not found: {item_id}")
        return self._item(row)

    def list_items(
        self,
        *,
        folder: str | None = None,
        pinned: bool | None = None,
        query: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> list[JsonDict]:
        clauses: list[str] = []
        params: list[object] = []
        if not include_deleted:
            clauses.append("deleted = 0")
        if folder is not None:
            clauses.append("folder = ?")
            params.append(folder)
        if pinned is not None:
            clauses.append("pinned = ?")
            params.append(int(pinned))
        if query:
            clauses.append("body LIKE ?")
            params.append(f"%{query}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self.conn.execute(
            f"SELECT * FROM clipboard_items{where} "
            "ORDER BY pinned DESC, created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._item(row) for row in rows]

    def set_item_state(
        self,
        item_id: int,
        *,
        body: str | None = None,
        folder: str | None = None,
        tags: str | None = None,
        pinned: bool | None = None,
        deleted: bool | None = None,
    ) -> JsonDict:
        self.get_item(item_id)  # raises KeyError if missing
        fields: list[str] = []
        params: list[object] = []
        if body is not None:
            fields.append("body = ?")
            params.append(body)
        if folder is not None:
            fields.append("folder = ?")
            params.append(folder)
        if tags is not None:
            fields.append("tags = ?")
            params.append(tags)
        if pinned is not None:
            fields.append("pinned = ?")
            params.append(int(pinned))
        if deleted is not None:
            fields.append("deleted = ?")
            params.append(int(deleted))
        if fields:
            params.append(item_id)
            self.conn.execute(
                f"UPDATE clipboard_items SET {', '.join(fields)} WHERE id = ?", params
            )
            self.conn.commit()
        return self.get_item(item_id)

    def soft_delete(self, item_id: int) -> JsonDict:
        return self.set_item_state(item_id, deleted=True)

    def mark_copied(self, item_id: int) -> JsonDict:
        """Record that an item was copied back to the clipboard (usage stamp)."""
        self.get_item(item_id)
        self.conn.execute(
            "UPDATE clipboard_items SET copied_at = datetime('now') WHERE id = ?",
            (item_id,),
        )
        self.conn.commit()
        return self.get_item(item_id)

    def import_items(self, items: list[JsonDict]) -> int:
        """Bulk insert exported items. Returns the number stored."""
        count = 0
        for item in items:
            body = item.get("body")
            if not body:
                continue
            self.conn.execute(
                """
                INSERT INTO clipboard_items (body, kind, source_app, source_window, folder, tags, pinned)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body,
                    item.get("kind", "text"),
                    item.get("source_app"),
                    item.get("source_window"),
                    item.get("folder"),
                    item.get("tags"),
                    int(bool(item.get("pinned", False))),
                ),
            )
            count += 1
        self.conn.commit()
        return count

    @staticmethod
    def _item(row: sqlite3.Row) -> JsonDict:
        return {
            "id": row["id"],
            "body": row["body"],
            "kind": row["kind"],
            "source_app": row["source_app"],
            "source_window": row["source_window"],
            "folder": row["folder"],
            "tags": row["tags"],
            "pinned": bool(row["pinned"]),
            "deleted": bool(row["deleted"]),
            "copied_at": row["copied_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
