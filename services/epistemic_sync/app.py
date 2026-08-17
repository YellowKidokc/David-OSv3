"""Credential-holding HTTP bridge for the Supra Infraque graph."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Supra Infraque PostgreSQL Sync", version="0.1.0")


class ConnectionRequest(BaseModel):
    connectionString: str | None = None


class GraphRequest(ConnectionRequest):
    graph: dict[str, Any] = Field(default_factory=dict)
    vaultId: str | None = None


def database_url(requested: str | None) -> str:
    return (requested or os.environ.get("EPISTEMIC_SYNC_DATABASE_URL", "")).strip()


def check_auth(api_key: str | None) -> None:
    expected = os.environ.get("EPISTEMIC_SYNC_API_TOKEN", "").strip()
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid helper API token")


def connect(url: str):
    if not url:
        raise ValueError("No database URL configured")
    return psycopg.connect(url, connect_timeout=8)


def ensure_schema(connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS supra_graph_records (
            collection TEXT NOT NULL,
            record_id TEXT NOT NULL,
            vault_id TEXT,
            payload JSONB NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (collection, record_id)
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_supra_graph_records_vault
        ON supra_graph_records (vault_id, collection)
    """)


def upsert_collection(connection, collection: str, records: Any, vault_id: str | None) -> int:
    if isinstance(records, dict):
        iterable = records.items()
    elif isinstance(records, list):
        iterable = ((str(item.get("id") or item.get("objectId") or item.get("relationId") or item.get("assignmentId") or item.get("eventId") or index), item) for index, item in enumerate(records))
    else:
        return 0
    count = 0
    for record_id, payload in iterable:
        if not isinstance(payload, dict):
            continue
        connection.execute(
            """INSERT INTO supra_graph_records (collection, record_id, vault_id, payload, synced_at)
               VALUES (%s, %s, %s, %s::jsonb, now())
               ON CONFLICT (collection, record_id) DO UPDATE SET
                 vault_id = EXCLUDED.vault_id, payload = EXCLUDED.payload, synced_at = now()""",
            (collection, str(record_id), vault_id, psycopg.types.json.Jsonb(payload)),
        )
        count += 1
    return count


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "supra-infraque-sync"}


@app.post("/test-connection")
def test_connection(request: ConnectionRequest, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_api_key)
    try:
        with connect(database_url(request.connectionString)) as connection:
            connection.execute("SELECT 1")
        return {"success": True, "message": "PostgreSQL connection succeeded."}
    except Exception as exc:
        return {"success": False, "error": type(exc).__name__ + ": " + str(exc)[:300]}


@app.post("/sync/graph")
def sync_graph(request: GraphRequest, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(x_api_key)
    graph = request.graph
    if not graph.get("schemaVersion"):
        raise HTTPException(status_code=400, detail="graph.schemaVersion is required")
    try:
        with connect(database_url(request.connectionString)) as connection:
            ensure_schema(connection)
            total = 0
            for collection in ("artifacts", "sourceSpans", "objects", "occurrences", "relations", "classifications", "changeEvents"):
                total += upsert_collection(connection, collection, graph.get(collection, {}), request.vaultId)
            connection.commit()
        return {"success": True, "recordsUpserted": total, "schemaVersion": graph["schemaVersion"], "syncedAt": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=type(exc).__name__ + ": " + str(exc)[:300]) from exc


def main() -> None:
    import uvicorn
    uvicorn.run("services.epistemic_sync.app:app", host=os.environ.get("EPISTEMIC_SYNC_HOST", "0.0.0.0"), port=int(os.environ.get("EPISTEMIC_SYNC_PORT", "8088")))
