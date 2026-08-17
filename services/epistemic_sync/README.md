# Supra Infraque Sync Helper

This service holds the PostgreSQL credential and accepts graph proposals from
the Obsidian plugin. It does not edit vault files and does not log database URLs.

Set these on the helper machine:

```text
EPISTEMIC_SYNC_DATABASE_URL=postgresql://user:password@127.0.0.1:5432/supra_infraque
EPISTEMIC_SYNC_HOST=0.0.0.0
EPISTEMIC_SYNC_PORT=8088
EPISTEMIC_SYNC_API_TOKEN=choose-a-local-token
```

Run from David-OS-v2:

```powershell
python -m pip install -e .
uvicorn services.epistemic_sync.app:app --host 0.0.0.0 --port 8088
```

Test the service without exposing credentials:

```powershell
Invoke-RestMethod http://127.0.0.1:8088/health
```

The service exposes `POST /test-connection` and `POST /sync/graph`. It creates
the separate `supra_graph_records` staging table in the configured database.
