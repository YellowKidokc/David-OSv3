# FIS HTML Intelligence

Read-only HTML corpus indexing and conversational retrieval for the File Intelligence System.

## Boundary

- HTML source files are never edited.
- SQLite is rebuildable index state.
- Search results cite exact source paths.
- AnythingLLM connects through a read-only MCP tool service.

## Commands

```powershell
python src\cli.py scan --root "G:\path\to\html-corpus"
python src\cli.py stats
python src\cli.py search "continuity architecture"
python src\cli.py series
python src\fis_mcp_server.py
```

The default database is `state\fis_html.sqlite`.

## AnythingLLM connection

The desktop MCP registry is configured at:

`C:\Users\David\AppData\Roaming\anythingllm-desktop\storage\plugins\anythingllm_mcp_servers.json`

Server name: `fis-html`

Available read-only tools:

- `search_html`
- `inspect_page`
- `list_html_series`
- `trace_continuity`
- `corpus_stats`
- `corpus_collections`

In AnythingLLM, use a workspace in **Agent** mode and enable the `fis-html` MCP server/tool set. The AI receives cited database results; it does not receive permission to edit the indexed HTML.

The `AXIOM` logical collection currently retains two distinct authority roles:

- `01_CANON` — `controlling-canon`
- `SRC_90_SYSTEM` — `preserved-system-source`

## Chat2DB connection

Chat2DB Community 5.3.0 is installed and includes its SQLite driver. Create a SQLite connection using the database file:

`D:\GitHub\FIS-HTML-Intelligence\state\fis_html.sqlite`

Prefer read-only mode. If Chat2DB exposes the full JDBC URL, use:

`jdbc:sqlite:file:D:/GitHub/FIS-HTML-Intelligence/state/fis_html.sqlite?mode=ro`

Start with the AI-facing views rather than the internal tables:

- `v_page_catalog`
- `v_series_catalog`
- `v_continuity_map`
- `v_collection_catalog`
- `schema_guide`

`sqlite-ai` is intentionally not loaded into the live database until its Windows build and Chat2DB JDBC extension-loading behavior pass on a disposable database copy.
