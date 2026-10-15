# Exact search in David OS

Implemented in the existing Hub API, not a parallel server.

- `POST /search/exact`: query, root aliases, optional file extensions, maximum_results (1–500), regex (default false), case_sensitive (default false).
- `GET /search/health`: executable, dependency paths and configured root aliases.
- Same service from the repository: `python scripts/search_exact.py "God cannot lie" --root lean --type lean --limit 50`.
- Health: `python scripts/search_exact.py --health`.
- Uses the existing Hub API authentication (`FIHUB_API_TOKEN`). No new listener is started.

Example request:

```json
{"query":"God cannot lie","roots":["lean"],"file_types":["md","lean"],"maximum_results":50}
```

Configuration is `config/search.json`, overridable with `DAVIDOS_SEARCH_CONFIG`.
Only configured aliases are accepted; arbitrary request paths and shell options are rejected.
The default searches this repository only. NAS roots require explicit selection.
The service runs rga with a bounded timeout, two search threads, bounded event queue and result count. Timeout, engine errors, oversized lines, and limits return explicit incomplete status. No automatic canon inference or ranking is performed.

Results contain absolute path, matched passage, line, modification time, canonical status and match offsets. Canonical status defaults to `unknown`; populate `canonical_register` with explicit absolute-path-to-status entries from an authoritative register. No automated canon synchronization is implemented.

For PDF/DOCX/archive/database results, line numbers refer to rga's extracted representation, not necessarily source page or original document lines. Archive member labels may appear inside passages. Preserve those labels when citing. Extension filters select outer files: include zip to search ZIP members. Search follows rga/rg default ignore behavior; it is not an exhaustive hidden-file or OCR scan.

## Installation on this machine

Official Windows rga 0.10.9 is installed under `runtime/search-tools/rga/`. It is the most recent Windows asset found among the inspected official releases; 0.10.10 had no Windows asset. Installed executable hash is in `config/search-tools.lock.json`.
Poppler 25.07.0-0 was installed through WinGet. Existing rg, Pandoc and FFmpeg are reused. The Poppler directory is explicitly configured for immediate use without restarting the shell.

Upstream supports Chocolatey/Scoop installation on Windows because those install dependencies. Neither was available here, so the official release was installed locally and missing Poppler supplied separately. Check `/search/health` after relocating the project. A full pinned portable installer is not implemented yet.

Upstream: https://github.com/phiresky/ripgrep-all

## Verification and remaining modes

Real fixtures cover Markdown literal/regex results, citations, no matches, limits, bad regex, root controls, API token enforcement, PDF, DOCX, ZIP members and SQLite text. Tests use reportlab and python-docx to create document fixtures.

Filename search and semantic retrieval remain future work. The existing `/semantic/score` endpoint classifies semantic addresses; it is not an embedding search engine. No desktop GUI wiring, relevance ranking, automatic canonical filtering, or corpus-wide indexing is claimed by this addition.
