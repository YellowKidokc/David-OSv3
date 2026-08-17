"""Persistence for file facts and folder pattern summaries."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

JsonDict = dict[str, Any]


def _dump(value: JsonDict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load(value: str) -> JsonDict:
    return json.loads(value)


class IntelligenceRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert_file_record(self, record: JsonDict) -> JsonDict:
        self.conn.execute(
            """
            INSERT INTO file_records (
                file_id, full_path, normalized_path, filename, extension, parent_folder_id,
                node_id, source_machine, raw_json, deterministic_json, ai_json, provenance_json,
                operational_json, policy_json, relationships_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_path) DO UPDATE SET
                file_id = excluded.file_id,
                full_path = excluded.full_path,
                filename = excluded.filename,
                extension = excluded.extension,
                parent_folder_id = excluded.parent_folder_id,
                node_id = excluded.node_id,
                source_machine = excluded.source_machine,
                raw_json = excluded.raw_json,
                deterministic_json = excluded.deterministic_json,
                ai_json = excluded.ai_json,
                provenance_json = excluded.provenance_json,
                operational_json = excluded.operational_json,
                policy_json = excluded.policy_json,
                relationships_json = excluded.relationships_json,
                updated_at = datetime('now')
            """,
            (
                record["identity"]["file_id"],
                record["identity"]["full_path"],
                record["identity"]["normalized_path"],
                record["identity"]["filename"],
                record["identity"]["extension"],
                record["identity"].get("parent_folder_id"),
                record["identity"]["node_id"],
                record["identity"].get("source_machine"),
                _dump(record["raw"]),
                _dump(record["deterministic"]),
                _dump(record["ai_advised"]),
                _dump(record["provenance"]),
                _dump(record["operational"]),
                _dump(record["policy"]),
                _dump(record["relationships"]),
            ),
        )
        self.conn.commit()
        return self.get_file_record(record["identity"]["normalized_path"])

    def get_file_record(self, normalized_path: str) -> JsonDict:
        row = self.conn.execute("SELECT * FROM file_records WHERE normalized_path = ?", (normalized_path,)).fetchone()
        if row is None:
            raise KeyError(f"file record not found: {normalized_path}")
        return self._file_record(row)

    def list_file_records_under(self, folder_path: str) -> list[JsonDict]:
        normalized_folder = folder_path.rstrip("/\\")
        prefix_forward = normalized_folder + "/%"
        prefix_backward = normalized_folder + "\\%"
        rows = self.conn.execute(
            "SELECT * FROM file_records WHERE normalized_path = ? OR normalized_path LIKE ? ORDER BY normalized_path",
            (normalized_folder, prefix_forward),
        ).fetchall()
        if not rows:
            rows = self.conn.execute(
                "SELECT * FROM file_records WHERE normalized_path = ? OR normalized_path LIKE ? ORDER BY normalized_path",
                (normalized_folder, prefix_backward),
            ).fetchall()
        return [self._file_record(row) for row in rows]

    def upsert_folder_summary(self, summary: JsonDict) -> JsonDict:
        self.conn.execute(
            """
            INSERT INTO folder_summaries (
                folder_id, folder_path, folder_profile_json, summary_json,
                provenance_json, action_pressure_json, last_summary_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(folder_path) DO UPDATE SET
                folder_id = excluded.folder_id,
                folder_profile_json = excluded.folder_profile_json,
                summary_json = excluded.summary_json,
                provenance_json = excluded.provenance_json,
                action_pressure_json = excluded.action_pressure_json,
                last_scan = datetime('now'),
                last_summary_version = excluded.last_summary_version
            """,
            (
                summary["folder_id"],
                summary["folder_path"],
                _dump(summary["folder_profile"]),
                _dump(summary["summary"]),
                _dump(summary["provenance"]),
                _dump(summary["action_pressure"]),
                summary["last_summary_version"],
            ),
        )
        self.conn.commit()
        return self.get_folder_summary(summary["folder_path"])

    def get_folder_summary(self, folder_path: str) -> JsonDict:
        row = self.conn.execute("SELECT * FROM folder_summaries WHERE folder_path = ?", (folder_path,)).fetchone()
        if row is None:
            raise KeyError(f"folder summary not found: {folder_path}")
        return {
            "folder_id": row["folder_id"],
            "folder_path": row["folder_path"],
            "folder_profile": _load(row["folder_profile_json"]),
            "summary": _load(row["summary_json"]),
            "provenance": _load(row["provenance_json"]),
            "action_pressure": _load(row["action_pressure_json"]),
            "last_scan": row["last_scan"],
            "last_summary_version": row["last_summary_version"],
        }

    @staticmethod
    def _file_record(row: sqlite3.Row) -> JsonDict:
        return {
            "identity": {
                "file_id": row["file_id"],
                "full_path": row["full_path"],
                "normalized_path": row["normalized_path"],
                "filename": row["filename"],
                "extension": row["extension"],
                "parent_folder_id": row["parent_folder_id"],
                "node_id": row["node_id"],
                "source_machine": row["source_machine"],
            },
            "raw": _load(row["raw_json"]),
            "deterministic": _load(row["deterministic_json"]),
            "ai_advised": _load(row["ai_json"]),
            "provenance": _load(row["provenance_json"]),
            "operational": _load(row["operational_json"]),
            "policy": _load(row["policy_json"]),
            "relationships": _load(row["relationships_json"]),
            "updated_at": row["updated_at"],
        }
