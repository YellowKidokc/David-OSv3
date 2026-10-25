# FIS Kernel Rust — Candidate Proof

This is a deliberately small, read-only proof of the proposed capability architecture.

It combines:

- `walkdir` for bounded recursive traversal;
- `blake3` for file fingerprints and exact-duplicate groups;
- `serde` / `serde_json` for stable artifacts;
- `clap` for a small callable interface.

Implemented folder-symptom checks:

- `S01` extension swamp;
- `S02` version sprawl;
- `S04` flat overload;
- `C01` byte-identical duplicate cluster;
- `I01` program-root danger;
- `I03` sensitive/config filename warning;
- `N04` path-length danger.

The program never moves, renames, deletes, or writes inside the scanned root. Output defaults to the operating-system temporary directory. A custom `--out` path is rejected if it is inside the scanned root.

```powershell
cargo run --release -- "D:\some-folder" --out "D:\FIS_REPORTS\run-001"
```

Outputs:

- `scan-report.json`
- `REPORT.md`

This is a candidate experiment, not a replacement for David-OSv3.
