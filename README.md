# David-OS v2
## Personal Infrastructure System

One SQLite database. One FastAPI server. Port 10000.

### Quick Start

```bash
cd D:\GitHub\David-OS-v2
pip install -e . --break-system-packages
dos-api --port 10000
```

### What It Does

- **File Intelligence** - watches folders, classifies files, suggests renames, review gate
- **Message Hub** - unified inbox for AI collaborators (Claude, GPT, Kimi, Gemini, Codex)
- **Memory Store** - vector-embedded searchable memory
- **Multi-Node** - desktop/NAS/laptop coordination with heartbeat

### Commands

| Command | What |
|---|---|
| `dos-api` | Start the hub API server |
| `dos-worker` | Start the job queue processor |
| `dos-watch` | Start native file watcher |
| `dos-poll` | Start polling file watcher |
| `dos-health` | Print node health JSON |
| `dos-top` | Top-of-Mind CLI (post messages, search memory) |

### Architecture

See `docs/ARCHITECTURE.md` for the full explainer.
