# Canon Query Overlay

Purpose: define where David's AI-queryable canon/change layer belongs.

Date: 2026-07-15
codex: architecture note
Status: PROPOSED / UNTESTED

## Decision

Use `David-OS` as the live program and control plane.

Do not write canon decisions into the large FIS crawl database directly. Treat the FIS crawl as a read-only source index.

## Existing Pieces

### Provider / AI layer

`D:\GitHub\David-OS\api\file_intelligence_hub\api\routes_openai_compat.py`

Already exposes OpenAI-compatible `/v1` chat endpoints and routes requests through pluggable providers.

`D:\GitHub\David-OS\api\file_intelligence_hub\services\provider_router.py`

Already supports OpenAI-compatible providers through `config/providers.json`, including OpenAI, DeepSeek, Ollama, LM Studio, or any compatible endpoint.

### Live hub database

`D:\GitHub\David-OS\api\.data\file-intelligence-hub.sqlite3`

Use this for live hub state, job cards, review queues, messages, memory, and routing.

### Large source index

`D:\DONT TOUCH BOOT UP\FIS\fis_catalog.db`

This is the full file census:

- about 2,456,988 files
- about 406,698 markdown files
- includes `\\192.168.2.50\z obsidian\...` paths

Treat this as read-only source discovery.

## New Piece Needed

Add a small canon overlay database, preferably:

`D:\GitHub\David-OS\api\.data\canon-overlay.sqlite3`

This database stores judgments, pins, proposed canon changes, and exportable decisions. It should reference source paths from FIS without copying the whole FIS catalog.

## Proposed Tables

### canon_items

Stores important claims or notes worth preserving.

Fields:

- `id`
- `title`
- `body`
- `item_type`: `claim`, `canon_change`, `open_problem`, `law_status`, `source_note`, `objection`, `todo`
- `status`: `candidate`, `accepted`, `rejected`, `needs_review`, `superseded`
- `importance`: 1-5
- `law_number`
- `bucket`
- `source_path`
- `source_db`
- `source_locator`
- `tags_json`
- `created_at`
- `updated_at`

### canon_decisions

Stores actual decisions that change canon or support status.

Fields:

- `id`
- `canon_item_id`
- `decision`
- `reason`
- `before_text`
- `after_text`
- `decided_by`
- `decided_at`
- `applied_path`
- `applied_at`

### canon_links

Stores relationships between items.

Fields:

- `id`
- `from_item_id`
- `to_item_id`
- `relation`: `supports`, `contradicts`, `duplicates`, `supersedes`, `depends_on`, `evidence_for`, `objection_to`
- `notes`

### canon_exports

Stores export runs so AI and humans can inspect the same decision set.

Fields:

- `id`
- `export_type`: `markdown`, `json`, `csv`
- `query_json`
- `output_path`
- `created_at`

## API Routes To Add

Add a new router:

`file_intelligence_hub/api/routes_canon_overlay.py`

Endpoints:

- `GET /canon/search?q=...`
- `POST /canon/items`
- `GET /canon/items/{id}`
- `PUT /canon/items/{id}`
- `POST /canon/items/{id}/decision`
- `GET /canon/export?status=accepted`
- `POST /canon/ai-query`

## AI Query Flow

1. User asks a question.
2. Query route searches:
   - canon overlay first;
   - live hub memory/messages second;
   - FIS catalog/source paths third.
3. Route reads the relevant source text only when needed.
4. Route sends a grounded prompt to the selected provider through `provider_router.send()`.
5. AI returns:
   - answer;
   - cited source paths;
   - proposed canon pins or change candidates.
6. User accepts/rejects changes into `canon_decisions`.

## Canon Safety Rules

- The AI may propose canon changes.
- The AI may not silently overwrite canon files.
- Every canon-changing action creates a `canon_decisions` row.
- A decision can be exported before file edits are applied.
- The huge FIS catalog remains read-only.
- Accepted canon changes should be applied to markdown files only after review.

## Why This Is The Right Home

`AI-HUB v2` is the desktop control surface.

`David-OS` is the backend intelligence hub.

`fis_catalog.db` is the file census.

`canon-overlay.sqlite3` is the missing judgment layer.

That division lets David talk to DeepSeek/OpenAI/local models about all indexed material while keeping canon edits deliberate, reversible, and exportable.
