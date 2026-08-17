"""Persistence for the Top of Mind multi-agent conversation relay."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

JsonDict = dict[str, Any]


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> object:
    return json.loads(value)


class TopOfMindRepo:
    """Store AI/tool sources and the message stream they share."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_source(
        self,
        source_id: str,
        *,
        label: str,
        kind: str = "ai",
        priority: int = 5,
        status: str = "active",
        muted: bool = False,
        paused: bool = False,
        metadata: JsonDict | None = None,
    ) -> JsonDict:
        self.conn.execute(
            """
            INSERT INTO top_sources (source_id, label, kind, status, priority, muted, paused, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                label = excluded.label,
                kind = excluded.kind,
                status = excluded.status,
                priority = excluded.priority,
                muted = excluded.muted,
                paused = excluded.paused,
                metadata_json = excluded.metadata_json
            """,
            (source_id, label, kind, status, priority, int(muted), int(paused), _dump(metadata or {})),
        )
        self.conn.commit()
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> JsonDict:
        row = self.conn.execute("SELECT * FROM top_sources WHERE source_id = ?", (source_id,)).fetchone()
        if row is None:
            raise KeyError(f"top source not found: {source_id}")
        return self._source(row)

    def list_sources(self) -> list[JsonDict]:
        rows = self.conn.execute("SELECT * FROM top_sources ORDER BY priority ASC, label ASC").fetchall()
        return [self._source(row) for row in rows]

    def set_source_state(
        self,
        source_id: str,
        *,
        status: str | None = None,
        muted: bool | None = None,
        paused: bool | None = None,
        priority: int | None = None,
    ) -> JsonDict:
        source = self.get_source(source_id)
        updates = {
            "status": status if status is not None else source["status"],
            "muted": muted if muted is not None else source["muted"],
            "paused": paused if paused is not None else source["paused"],
            "priority": priority if priority is not None else source["priority"],
        }
        self.conn.execute(
            "UPDATE top_sources SET status = ?, muted = ?, paused = ?, priority = ? WHERE source_id = ?",
            (updates["status"], int(updates["muted"]), int(updates["paused"]), updates["priority"], source_id),
        )
        self.conn.commit()
        return self.get_source(source_id)

    def stop_all_sources(self) -> list[JsonDict]:
        self.conn.execute("UPDATE top_sources SET status = 'stopped', paused = 1")
        self.conn.commit()
        return self.list_sources()

    def post_message(
        self,
        *,
        source_id: str,
        body: str,
        source_label: str | None = None,
        source_code: int | None = None,
        type_code: int = 30001,
        role: str = "assistant",
        priority: int | None = None,
        priority_code: int = 40003,
        wall: str = "main",
        wall_code: int = 50001,
        folder: str = "Main",
        folder_code: int = 60001,
        pinned: bool = False,
        combined_from: list[int] | None = None,
        metadata: JsonDict | None = None,
    ) -> JsonDict:
        try:
            source = self.get_source(source_id)
        except KeyError:
            source = self.upsert_source(source_id, label=source_label or source_id)
        cur = self.conn.execute(
            """
            INSERT INTO top_messages (
                source_id, source_label, source_code, type_code, role, body, priority, priority_code,
                wall, wall_code, folder, folder_code, pinned, combined_from_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source_label or source["label"],
                source_code,
                type_code,
                role,
                body,
                priority if priority is not None else int(source["priority"]),
                priority_code,
                wall,
                wall_code,
                folder,
                folder_code,
                int(pinned),
                _dump(combined_from or []),
                _dump(metadata or {}),
            ),
        )
        self.conn.commit()
        return self.get_message(int(cur.lastrowid))

    def get_message(self, message_id: int) -> JsonDict:
        row = self.conn.execute("SELECT * FROM top_messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(f"top message not found: {message_id}")
        return self._message(row)

    def list_messages(
        self,
        *,
        source_id: str | None = None,
        wall: str | None = None,
        folder: str | None = None,
        pinned: bool | None = None,
        include_archived: bool = False,
        limit: int = 75,
    ) -> list[JsonDict]:
        clauses: list[str] = []
        params: list[object] = []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        if wall:
            clauses.append("wall = ?")
            params.append(wall)
        if folder:
            clauses.append("folder = ?")
            params.append(folder)
        if pinned is not None:
            clauses.append("pinned = ?")
            params.append(int(pinned))
        if not include_archived:
            clauses.append("archived = 0")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(
            f"SELECT * FROM top_messages{where} ORDER BY pinned DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._message(row) for row in rows]

    def set_message_state(
        self,
        message_id: int,
        *,
        pinned: bool | None = None,
        archived: bool | None = None,
        wall: str | None = None,
        folder: str | None = None,
    ) -> JsonDict:
        message = self.get_message(message_id)
        self.conn.execute(
            """
            UPDATE top_messages
            SET pinned = ?, archived = ?, wall = ?, folder = ?
            WHERE id = ?
            """,
            (
                int(message["pinned"] if pinned is None else pinned),
                int(message["archived"] if archived is None else archived),
                wall if wall is not None else message["wall"],
                folder if folder is not None else message["folder"],
                message_id,
            ),
        )
        self.conn.commit()
        return self.get_message(message_id)

    def combine_messages(
        self,
        message_ids: list[int],
        *,
        source_id: str = "top-of-mind",
        source_label: str = "Top of Mind",
        wall: str = "main",
        folder: str = "Main",
    ) -> JsonDict:
        messages = [self.get_message(message_id) for message_id in message_ids]
        body = "\n\n".join(f"[{message['source_label']}] {message['body']}" for message in messages)
        return self.post_message(
            source_id=source_id,
            source_label=source_label,
            role="system",
            body=body,
            wall=wall,
            folder=folder,
            pinned=True,
            combined_from=message_ids,
            metadata={"operation": "combine"},
        )

    @staticmethod
    def _source(row: sqlite3.Row) -> JsonDict:
        return {
            "source_id": row["source_id"],
            "label": row["label"],
            "kind": row["kind"],
            "status": row["status"],
            "priority": row["priority"],
            "muted": bool(row["muted"]),
            "paused": bool(row["paused"]),
            "metadata": _load(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _message(row: sqlite3.Row) -> JsonDict:
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "source_label": row["source_label"],
            "source_code": row["source_code"] if "source_code" in row.keys() else None,
            "type_code": row["type_code"] if "type_code" in row.keys() else 30001,
            "role": row["role"],
            "body": row["body"],
            "priority": row["priority"],
            "priority_code": row["priority_code"] if "priority_code" in row.keys() else 40003,
            "wall": row["wall"],
            "wall_code": row["wall_code"] if "wall_code" in row.keys() else 50001,
            "folder": row["folder"],
            "folder_code": row["folder_code"] if "folder_code" in row.keys() else 60001,
            "pinned": bool(row["pinned"]),
            "archived": bool(row["archived"]),
            "combined_from": _load(row["combined_from_json"]),
            "metadata": _load(row["metadata_json"]),
            "created_at": row["created_at"],
        }
