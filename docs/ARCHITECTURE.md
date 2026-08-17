# File Intelligence Hub — Architectural Explainer
## The Brain of David-OS

**Location:** `D:\GitHub\tom_fis_api\apps\api\file_intelligence_hub\`  
**Purpose:** This is THE BRAIN. Every other system (React app, AHK overlay, NLP stations, LLM exploration layer) talks to this. If you understand this, you understand what holds everything together.  
**Date:** July 7, 2026 | David Lowe (POF 2828) + Opus

---

## How to Read This Document

This document explains the architecture of the File Intelligence Hub completely — what each module does, how they connect, what data flows where, and what the system is trying to accomplish. You should be able to understand the entire subsystem from this document alone without reading a single line of code.

If you're an AI being asked to extend, debug, or build on this system, start here. If you need implementation details after understanding the architecture, THEN read the code files referenced in each section.

---

## The Big Picture

The File Intelligence Hub is a FastAPI application backed by SQLite. It runs on port 10000. It does six things:

1. **Watches folders** for file changes (create, modify, move, delete)
2. **Processes file events** through a worker pipeline (classify → hash → suggest rename → review gate → execute)
3. **Stores a unified message stream** where all AI sources (Claude, GPT, Kimi, Gemini, human) post messages into shared walls and folders
4. **Routes messages** to AI personas using an OpenAI-compatible API (so Mattermost and other tools can talk to it)
5. **Manages memory** with vector embeddings for semantic search
6. **Tracks node health** across multiple machines (NAS, desktop, laptop) with heartbeat and failover

Everything is SQLite. No Postgres dependency for the hub itself (Postgres exists separately for the Theophysics vault data). WAL mode is enabled so reads don't block writes.

---

## Module Map

```
file_intelligence_hub/
├── api/                 ← FastAPI routes (the HTTP surface)
│   ├── app.py           ← App factory, mounts all routers
│   ├── security.py      ← Bearer token middleware
│   ├── routes_top_of_mind.py    ← Message stream (sources, messages, walls, folders)
│   ├── routes_openai_compat.py  ← OpenAI-compatible router with persona routing
│   ├── routes_nodes.py          ← Node heartbeat, health, peer discovery
│   ├── routes_memory.py         ← Memory store with vector search
│   ├── routes_intelligence.py   ← File records and folder summaries (read)
│   ├── routes_file_cache.py     ← Desktop file cache (index/search)
│   ├── routes_file_actions.py   ← File operations (copy, move, delete with review)
│   ├── routes_jobs.py           ← Job queue management
│   ├── routes_commands.py       ← Shell command execution with review gates
│   ├── routes_folders.py        ← Top of Mind folder management
│   ├── routes_prediction.py     ← Prediction engine endpoints
│   └── routes_api_actions.py    ← API action registry
│
├── storage/             ← Data access layer (all SQLite operations)
│   ├── db.py            ← Connection, schema, migrations (v1-v11)
│   ├── top_of_mind_repo.py      ← Sources + messages CRUD
│   ├── job_repo.py              ← Job queue CRUD
│   ├── memory_repo.py           ← Memory items CRUD + embedding search
│   ├── intelligence_repo.py     ← File records + folder summaries
│   ├── desktop_file_cache_repo.py ← Fast file index for desktop search
│   ├── folder_repo.py           ← Top of Mind folder hierarchy
│   └── node_repo.py             ← Node registry
│
├── core/                ← Business logic orchestration
│   ├── job_manager.py   ← THE BRAIN: file event → classify → hash → rename → review
│   └── review_gate.py   ← Decides if an action needs human approval
│
├── workers/             ← Individual processing units
│   ├── runner.py        ← Job queue runner (polls for queued jobs, dispatches to workers)
│   ├── classify_worker.py       ← Classify a file by extension, name patterns, content
│   ├── hash_worker.py           ← SHA-256 hash for dedup and integrity
│   ├── rename_worker.py         ← Suggest and execute intelligent file renames
│   ├── folder_summary_worker.py ← Generate folder-level intelligence summaries
│   ├── file_action_worker.py    ← Execute file operations (copy, move, etc.)
│   ├── command_worker.py        ← Execute shell commands with safety checks
│   ├── embedding_worker.py      ← Generate vector embeddings for memory items
│   ├── asset_pair_worker.py     ← Match related files (e.g., .srt + .mp4)
│   ├── review_worker.py         ← Process human review decisions
│   └── parsers.py               ← File content parsers (extract text from various formats)
│
├── config/              ← Configuration
│   └── folder_profiles.py       ← Per-folder processing rules (what to watch, how to name)
│
├── intelligence/        ← Higher-level analysis
│   ├── file_feature_builder.py  ← Extract features from a single file
│   ├── folder_feature_builder.py ← Extract features from a folder of files
│   └── prediction_engine.py     ← Predict file categories, suggest actions
│
├── rules/               ← Decision rules
│   └── thresholds.py    ← When does a rename need review? Confidence thresholds.
│
├── watchers/            ← Filesystem monitoring
│   ├── runner.py        ← Polling watcher (scans folders, detects changes)
│   ├── native.py        ← Native OS file events (Windows ReadDirectoryChangesW)
│   └── event_normalizer.py ← Normalize raw events into standard format
│
├── cli.py               ← Command-line interface (fihub-api, fihub-top)
└── __init__.py
```

---

## Data Flow: How a File Event Becomes Intelligence

This is the core loop. Everything else is support for this.

```
1. WATCHER detects file change
   │  (watchers/runner.py → PollingWatcher.poll_once())
   │  Scans configured folders every N seconds
   │  Compares current snapshot to previous (mtime + size)
   │  Detects: created, modified, deleted, moved
   │
   ▼
2. EVENT NORMALIZER standardizes the raw event
   │  (watchers/event_normalizer.py → normalize_file_event())
   │  Output: {event_type, path, dest_path, is_directory, source}
   │
   ▼
3. JOB MANAGER ingests the event
   │  (core/job_manager.py → ingest_file_event())
   │  Creates a job in the jobs table (status: queued)
   │  Matches the file path against folder profiles
   │
   ▼
4. WORKER PIPELINE processes the job
   │  (core/job_manager.py → process_file_event())
   │
   │  Step 4a: HASH the file (workers/hash_worker.py)
   │           SHA-256 for dedup and integrity checking
   │
   │  Step 4b: CLASSIFY the file (workers/classify_worker.py)
   │           Extension, name patterns, content analysis
   │           Output: {type, category, confidence, features}
   │
   │  Step 4c: SUGGEST RENAME (workers/rename_worker.py)
   │           Based on classification + folder profile rules
   │           Output: {current_name, suggested_name, confidence, reason}
   │
   ▼
5. REVIEW GATE evaluates the suggestion
   │  (core/review_gate.py → evaluate_rename())
   │  Uses rules/thresholds.py to decide:
   │    - High confidence + safe folder → auto-execute
   │    - Low confidence or risky folder → require human review
   │  If review required: creates review_item, job status → waiting_review
   │  If auto-approved: proceeds to execution
   │
   ▼
6. EXECUTE (if approved)
   │  (workers/rename_worker.py → execute_rename())
   │  Performs the actual file rename
   │  Logs to ledger_entries (before/after, reversible)
   │
   ▼
7. LEDGER records everything
   │  (storage/job_repo.py → add_ledger_entry())
   │  Every action has a before state and after state
   │  Every action is reversible from the ledger
```

---

## Data Flow: How Messages Move Through the System

This is the unified inbox / AI communication path.

```
1. MESSAGE arrives from any source
   │  Sources: Claude, GPT, Kimi, Gemini, Mattermost, AHK, human
   │  Via: POST /top-of-mind/messages
   │  Or:  POST /v1/chat/completions (OpenAI-compatible)
   │
   ▼
2. SOURCE is registered/updated
   │  (storage/top_of_mind_repo.py → upsert_source())
   │  Each source has: id, label, kind, priority, status, muted, paused
   │
   ▼
3. MESSAGE is stored
   │  (storage/top_of_mind_repo.py → post_message())
   │  Fields: source_id, role, body, wall, folder, priority, pinned
   │  Walls = top-level grouping (main, ai-crew, research)
   │  Folders = second-level grouping within a wall
   │
   ▼
4. If via OpenAI-compatible route: PERSONA ROUTING
   │  (api/routes_openai_compat.py → _select_persona())
   │  Detects target persona from:
   │    a) Message prefix: "/kimi ...", "@opus ...", "codex: ..."
   │    b) Metadata fields: persona, channel_name, etc.
   │    c) Default: Kimi (coordinator role)
   │  Adds persona system message to the conversation
   │
   ▼
5. If downstream provider configured: FORWARD
   │  Currently: DeepSeek (via DEEPSEEK_API_KEY env var)
   │  Future: route to correct provider based on persona
   │  Response stored back as a message from the router
   │
   ▼
6. RESPONSE returned to caller
   │  OpenAI-compatible format: {choices: [{message: {content: ...}}]}
   │  Supports streaming (SSE) and non-streaming
```

---

## SQLite Schema Overview

The database has 11 migration versions. Here's what exists at v11:

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `schema_meta` | Schema version tracking | key, value |
| `schema_migrations` | Migration history | version, applied_at |
| `jobs` | Job queue for all async work | type, status, priority, payload_json, result_json, attempts, leased_by |
| `job_events` | State transition log for jobs | job_id, from_status, to_status, event_type |
| `review_items` | Human review queue | job_id, status, reason, action, payload_json |
| `ledger_entries` | Audit trail (before/after for every action) | job_id, action, before_json, after_json |
| `file_records` | Full file intelligence records | file_id, full_path, node_id, raw/deterministic/ai/provenance/operational/policy/relationships JSON |
| `folder_summaries` | Folder-level intelligence | folder_id, folder_path, summary_json, action_pressure_json |
| `nodes` | Machine registry for multi-node setup | node_id, node_role, capabilities, status, last_seen |
| `repair_log` | File repair/recovery history | repair_type, scope, artifact_path, outcome |
| `top_sources` | AI and tool source registry | source_id, label, kind, status, priority, muted, paused |
| `top_messages` | Unified message stream | source_id, role, body, wall, folder, pinned, archived |
| `top_folders` | Folder hierarchy for message organization | name, slug, parent_id, wall, owner_id, visibility |
| `memory_items` | Searchable memory store | title, body, tags, embedding_json |
| `desktop_file_cache` | Fast file index for desktop search | normalized_path, filename, extension, tier, tags |
| `routing_rules` | Message routing configuration | match_json, target_json, priority |
| `routing_decisions` | Routing decision audit trail | message_id, selected_targets, matched_rules |

---

## The Nine AI Personas

The OpenAI-compatible router supports nine personas. Each has aliases (for prefix routing) and a system prompt. The persona determines how the router behaves when forwarding to a downstream LLM.

| Persona | Aliases | Role |
|---------|---------|------|
| Kimi | kimi, kimmy, k | Default coordinator. Short operational answers. |
| Codex | codex, code, c | Code, files, APIs, tests, shell commands. |
| Fabel | fabel, fable, f | Site pipelines, content structure, workflow. |
| Gemini | gemini, g | Broad verification, integration checks. |
| GPT | gpt, gpt-5.5 | General reasoning, planning, summaries. |
| Opus | opus, 4.8, 4.7 | Deep reasoning, canon, editorial, theorems. |
| Sonnet | sonnet | Balanced implementation, writing polish. |
| Anti-Gravity | anti-gravity, ag | UI, layout, browser behavior, packaging. |
| Hakui | hakui, h | Fast lightweight answers, quick checks. |

Routing priority: (1) message prefix (`/kimi`, `@opus`), (2) metadata fields, (3) default to Kimi.

---

## Multi-Node Architecture

The system is designed to run on multiple machines with one primary writer:

- **Heartbeat:** `POST /nodes/heartbeat` — local node registers itself
- **Peer heartbeat:** `POST /nodes/peer-heartbeat` — remote node announces its presence
- **Health check:** `GET /nodes/health` — check local system health
- **Node list:** `GET /nodes` — list all known nodes

Each node has: node_id, node_role (primary/peer), capabilities, status, last_seen, resource info, queue depth, version, build signature.

The boot sequence (from ARCHITECTURE.md): ping NAS → if alive, register as peer → if dead, promote to primary → when NAS returns, sync and demote.

---

## What's Missing (Known Gaps)

1. **Knowledge graph tables** — `kg_nodes` and `kg_edges` (defined in ARCHITECTURE.md Section 5, not yet in db.py migrations)
2. **Multi-provider routing** — Only DeepSeek is wired as a downstream. Claude, OpenAI, and Kimi API backends are not connected (and won't be — David uses desktop apps, not APIs, for cost reasons)
3. **AHK bridge integration** — No endpoint for "paste this message into window X and capture the response"
4. **YouTube intake endpoint** — No route for ingesting transcripts
5. **OKF navigation index** — No route for the hierarchical summary navigation
6. **Line separator parsing** — Not yet in the pipeline
7. **Boot sequence automation** — Described in architecture but not implemented in code

---

## How to Run It

```powershell
cd D:\GitHub\tom_fis_api\apps\api
pip install -e . --break-system-packages
fihub-api --host 0.0.0.0 --port 10000
```

For the worker queue runner:
```powershell
python -m file_intelligence_hub.workers.runner --db .data/file-intelligence-hub.sqlite3 --forever
```

For the file watcher:
```powershell
python -m file_intelligence_hub.watchers.runner --db .data/file-intelligence-hub.sqlite3 --profiles config/folder_profiles.json --forever
```

Environment variables:
- `FIHUB_DB_PATH` — SQLite database location (default: `.data/file-intelligence-hub.sqlite3`)
- `DEEPSEEK_API_KEY` — Enable DeepSeek forwarding in the OpenAI-compat router
- `DEEPSEEK_MODEL` — Model name (default: `deepseek-v4-flash`)
- `DEEPSEEK_BASE_URL` — API base URL
- `DEEPSEEK_TIMEOUT_SECONDS` — Request timeout (default: 60)

---
---

# TEMPLATE: How to Write an Architectural Explainer for Any Subsystem

## Instructions for AI Collaborators

David wants every major folder in David-OS to have an architectural explainer like the one above. Here's how to write one. Follow this template exactly.

### Your Task

You will be given a folder path. Read every file in that folder. Then write a document that explains the architecture SO CLEARLY that another AI can understand the entire subsystem without reading any code.

### Document Structure (follow this order)

1. **Header block** — Location, purpose, date. One sentence on why this subsystem matters.

2. **The Big Picture** — What does this subsystem DO? Not what files it has, but what PROBLEM it solves. What are the 3-6 things it does? Write this as a numbered list of capabilities.

3. **Module Map** — ASCII tree of the folder structure with one-line descriptions. Every file gets a description. No file is left unexplained.

4. **Data Flow Diagrams** — The core paths that data takes through the system. Use ASCII art with numbered steps and annotations. There should be at least one data flow diagram for each major capability. Show: where data enters, what transforms it, where it ends up.

5. **Data Schema** — If there are databases, config files, or structured data: document the schema. Table names, key fields, relationships. If it's SQLite, show the tables. If it's JSON configs, show the structure.

6. **Key Concepts** — Domain-specific terms, patterns, or abstractions that someone needs to understand. If the code uses concepts like "review gate," "folder profiles," "persona routing" — define them here.

7. **What's Missing** — Known gaps, TODOs, things that are described in the master ARCHITECTURE.md but not yet built in this subsystem. Be honest about what doesn't exist yet.

8. **How to Run It** — Commands to start, test, and verify the subsystem. Environment variables. Dependencies.

### Rules

- **No code in the explainer.** Reference file paths for implementation details, but the explainer itself should be pure architecture — concepts, flows, schemas, relationships.
- **Be specific about connections.** Don't say "this connects to the hub." Say "this calls POST /top-of-mind/messages with source_id='youtube-intake' and wall='research'."
- **Name the failure modes.** What breaks if this subsystem goes down? What depends on it? What does it depend on?
- **Write for an AI reader.** Assume the reader is an LLM that has never seen the codebase. It needs to understand the INTENT and ARCHITECTURE well enough to extend or debug the system. It does NOT need to see the code — it can read the code later if needed.
- **Reference the master architecture.** If this subsystem implements something described in `David-OS/core/ARCHITECTURE.md`, say which section. Don't repeat the master doc — point to it.

### Naming Convention

Save the explainer as `ARCHITECTURE.md` inside the folder it describes. Example:
- `D:\GitHub\David-OS\pipeline\ARCHITECTURE.md`
- `D:\GitHub\David-OS\ahk\ARCHITECTURE.md`
- `D:\GitHub\David-OS\app\ARCHITECTURE.md`

### Quality Check

Before you're done, verify:
- [ ] Could an AI that has never seen this codebase understand what the subsystem does?
- [ ] Could it identify which file to modify if asked to add a feature?
- [ ] Could it explain the data flow to David in plain English?
- [ ] Are all files in the folder mentioned and explained?
- [ ] Are all connections to other subsystems documented?

If any answer is no, the explainer isn't done.
