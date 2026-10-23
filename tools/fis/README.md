# FIS components in David-OSv3

Preserved copies of the existing projects; originals remain at their previous locations.

- `FIS-Kernel-Rust`: candidate read-only folder scanner (Rust source and lockfile; build output excluded).
- `FIS-Kernel-Rust-TEST-OUTPUT`: historical scan artifacts, not a fresh validation.
- `FIS-HTML-Intelligence`: HTML extraction, SQLite indexing, search, and read-only MCP retrieval.

The HTML index database is a consistent SQLite snapshot of the original, not an automatically synchronized database. Its stored source paths retain their original locations. Existing AnythingLLM configuration continues to use the original project. No services or corpus scans were started.

These components do not yet generate the requested single theology-folder HTML overview. That integration remains to be implemented using the selected folder scope.

From this directory:

```powershell
python .\FIS-HTML-Intelligence\src\cli.py --help
cargo run --manifest-path .\FIS-Kernel-Rust\Cargo.toml --release -- "<selected-folder>" --out "<separate-report-folder>"
```

The Rust scanner fingerprints with BLAKE3; existing David-OS provenance may use SHA-256. Preserve the algorithm label when connecting records.
