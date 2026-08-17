"""Persistence for Top of Mind memory and future vector search."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from hub.workers.embedding_worker import cosine_similarity, embed_text

JsonDict = dict[str, Any]


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load(value: str | None) -> object:
    return json.loads(value) if value else None


class MemoryRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create_item(
        self,
        *,
        title: str,
        body: str,
        source: str = "api",
        folder: str = "Memory",
        tags: list[str] | None = None,
        metadata: JsonDict | None = None,
        embedding: list[float] | None = None,
    ) -> JsonDict:
        cur = self.conn.execute(
            """
            INSERT INTO memory_items (title, body, source, folder, tags_json, metadata_json, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, body, source, folder, _dump(tags or []), _dump(metadata or {}), _dump(embedding) if embedding else None),
        )
        self.conn.commit()
        return self.get_item(int(cur.lastrowid))

    def get_item(self, item_id: int) -> JsonDict:
        row = self.conn.execute("SELECT * FROM memory_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(f"memory item not found: {item_id}")
        return self._item(row)

    def list_items(self, *, folder: str | None = None, source: str | None = None, limit: int = 75) -> list[JsonDict]:
        clauses: list[str] = []
        params: list[object] = []
        if folder:
            clauses.append("folder = ?")
            params.append(folder)
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(f"SELECT * FROM memory_items{where} ORDER BY id DESC LIMIT ?", params).fetchall()
        return [self._item(row) for row in rows]

    def search(self, query: str, *, limit: int = 25) -> list[JsonDict]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return []
        rows = self.conn.execute("SELECT * FROM memory_items ORDER BY id DESC LIMIT 1000").fetchall()
        scored: list[tuple[int, JsonDict]] = []
        for row in rows:
            item = self._item(row)
            haystack = f"{item['title']} {item['body']} {' '.join(item['tags'])}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                result = dict(item)
                result["score"] = score
                scored.append((score, result))
        scored.sort(key=lambda pair: (-pair[0], -int(pair[1]["id"])))
        return [item for _, item in scored[: max(1, min(limit, 100))]]

    def update_embedding(self, item_id: int, embedding: list[float] | None = None) -> JsonDict:
        item = self.get_item(item_id)
        vector = embedding or embed_text(f"{item['title']}\n\n{item['body']}")
        self.conn.execute("UPDATE memory_items SET embedding_json = ? WHERE id = ?", (_dump(vector), item_id))
        self.conn.commit()
        return self.get_item(item_id)

    def embed_pending(self, *, limit: int = 100) -> list[JsonDict]:
        rows = self.conn.execute(
            "SELECT * FROM memory_items WHERE embedding_json IS NULL ORDER BY id LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
        return [self.update_embedding(int(row["id"])) for row in rows]

    def vector_search(self, query: str, *, limit: int = 25) -> list[JsonDict]:
        query_vector = embed_text(query)
        rows = self.conn.execute("SELECT * FROM memory_items WHERE embedding_json IS NOT NULL ORDER BY id DESC").fetchall()
        scored: list[tuple[float, JsonDict]] = []
        for row in rows:
            item = self._item(row)
            score = cosine_similarity(query_vector, item["embedding"] or [])
            if score > 0:
                result = dict(item)
                result["score"] = round(score, 6)
                scored.append((score, result))
        scored.sort(key=lambda pair: (-pair[0], -int(pair[1]["id"])))
        return [item for _, item in scored[: max(1, min(limit, 100))]]

    @staticmethod
    def _item(row: sqlite3.Row) -> JsonDict:
        return {
            "id": row["id"],
            "title": row["title"],
            "body": row["body"],
            "source": row["source"],
            "folder": row["folder"],
            "tags": _load(row["tags_json"]),
            "metadata": _load(row["metadata_json"]),
            "embedding": _load(row["embedding_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
