# API Contract v0

This is the first target contract for the hub API.

## Nodes

### `POST /nodes/heartbeat`

Receives node status from Synology, desktop, laptop, or service agents.

```json
{
  "node_id": "desktop",
  "name": "Desktop",
  "role": "backup-hub-and-watcher",
  "status": "online",
  "base_url": "http://127.0.0.1:10000"
}
```

## File Events

### `POST /events/file`

Receives watcher events. Watchers should not decide actions.

```json
{
  "event_id": "optional-uuid",
  "source_node_id": "desktop",
  "event_type": "created",
  "path": "D:/example/file.pdf",
  "old_path": null,
  "extension": ".pdf",
  "size_bytes": 123456,
  "file_hash": null,
  "folder_profile": "downloads"
}
```

## Scans

### `POST /scan/folder`

Runs or records a folder scan.

```json
{
  "source_node_id": "desktop",
  "target_path": "D:/example",
  "mode": "read_only"
}
```

## Clipboard

### `POST /clipboard/save`

Saves a clipboard item into the hub cache.

```json
{
  "source_node_id": "desktop",
  "source_app": "AutoHotkey",
  "content_type": "text/plain",
  "content": "message text",
  "pinned": false,
  "priority": 0
}
```

### `GET /clipboard/history`

Returns recent clipboard entries the caller can access.

### `POST /clipboard/{id}/copy-out`

Marks a clipboard item for AHK or the desktop bridge to copy back out.

### `POST /clipboard/{id}/send`

Routes clipboard content to an active agent through dispatch.

## Actions

### `POST /actions/propose`

Creates an action proposal. This does not execute the action.

```json
{
  "action_type": "rename",
  "path": "D:/example/badname.pdf",
  "target_path": "D:/example/Good Name.pdf",
  "reason": "Filename was unreadable and document title was detected.",
  "confidence": 0.82,
  "requires_approval": true
}
```

## Command Line

### `POST /commands/jobs`

Creates a command job. Dangerous commands require approval.

```json
{
  "source_node_id": "desktop",
  "command": "python scripts/task.py --dry-run",
  "working_dir": "D:/GitHub/TOP AI FIS",
  "requires_approval": true
}
```

### `POST /commands/jobs/{job_id}/approve`

Approves a pending command job.

### `POST /commands/jobs/{job_id}/cancel`

Cancels a queued or running command job.

## Dispatch / Agents

### `POST /dispatch/jobs`

Routes a message to Claude, Gemini, Codex, Kimi, GPT, Operator, Clipboard, or another bridge target.

```json
{
  "source": "react",
  "target_agent": "claude",
  "target_route": "desktop-ahk",
  "message": "Summarize this file event.",
  "priority": 3
}
```

### `POST /agents/stop-all`

Broadcasts a stop request to active agents/bridges.

### `POST /agents/{agent_id}/pause`

Pauses one route.

### `POST /agents/{agent_id}/resume`

Resumes one route.

## Knowledge Banks

### `POST /knowledge-banks`

Creates a permissioned knowledge bank.

### `POST /knowledge-banks/{bank_id}/items`

Attaches clipboard, message, file, or text content to a bank.

### `GET /knowledge-banks/{bank_id}/search?q=...`

Searches indexed bank content subject to caller permissions.

## Vectorization

## Semantic Addressing

### `POST /semantic/score`

Runs the promoted legacy FIS 10D semantic scorer on either a real file path or
pre-extracted text. This is deterministic and does not call an external AI API.

```json
{
  "path": "D:/example/file.md",
  "text": "Optional pre-extracted text if the caller already read the file."
}
```

Returns:

```json
{
  "semantic_address": {
    "source": "legacy-fis-semantic-scorer",
    "variables": ["G", "M", "E", "S", "T", "K", "R", "Q", "F", "C"],
    "vector": [0, 1, 0, 0, 0, 2, 0, 0, 1, 0],
    "dominant": ["K", "F"],
    "coord_hash_full": "KF-0000-1W",
    "human_score": "G0|M1|E0|S0|T0|K2|R0|Q0|F1|C0",
    "meta": {
      "path": "BUSINESS/WORK/CAPTURE/ACTIVE"
    }
  }
}
```

### `POST /vectors/chunk`

Chunks text, files, clipboard content, or messages.

### `POST /vectors/embed`

Creates embeddings for approved chunks.

### `GET /vectors/search?q=...&namespace=...`

Runs similarity search inside allowed vector namespaces.

## MCP

### `GET /mcp/tools`

Lists enabled MCP tools visible to the caller.

### `POST /mcp/tools/call`

Calls an approved MCP tool and stores the call history.
