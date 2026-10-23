# FIS Intelligence — David-OSv3

One package combining the existing HTML intelligence code, Rust filesystem kernel, and historical test artifacts. Original projects and earlier copied bundles remain preserved. Use this directory for further integration.

## Commands

```powershell
.\FIS.bat html --help
.\FIS.bat html stats
.\FIS.bat html search "grace"
.\FIS.bat html scan --root "<explicitly selected folder>"
.\FIS.bat kernel "<explicitly selected folder>" --out "<separate output folder>"
.\FIS.bat mcp
```

Python runs the HTML tools; Cargo builds/runs the Rust kernel. MCP additionally requires the Python `mcp` package. No dependency installation or service startup was performed during consolidation.

## Layout

- `src/`: HTML extraction, indexing, retrieval, and MCP service.
- `rust/`: filesystem kernel source and locked dependencies; build artifacts excluded.
- `state/`: consistent SQLite snapshot of the original HTML index, checked with `PRAGMA quick_check`.
- `tests/`: original HTML index tests.
- `reports/historical-rust-test/`: preserved historical reports, not a fresh scan.
- `docs/`: original documentation for provenance; original absolute connection paths describe the former locations.
- `COPY_RECEIPT.json`: source paths and hash verification.

HTML remains the document format. SQLite is auxiliary search state. The package does not yet generate the requested collection HTML connecting all papers in the selected theology folder. Consolidation does not modify any corpus, start scans, or change AnythingLLM configuration. The database is a snapshot, not a synchronization service. Rust uses BLAKE3; the HTML index uses SHA-256. Keep these hash types distinct.
