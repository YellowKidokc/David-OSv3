# Theophysics Test Stack Notes

This repo now has two levels of test coverage for the Theophysics work:

1. Normal Python/API tests for David-OS itself.
2. A portable artifact verifier for downloaded Lean/proof/prediction bundles.

The verifier lives at:

```powershell
python scripts\verify_theophysics_bundle.py <bundle-root>
```

Useful options:

```powershell
python scripts\verify_theophysics_bundle.py <bundle-root> --run-pytest
python scripts\verify_theophysics_bundle.py <bundle-root> --run-lake
python scripts\verify_theophysics_bundle.py <bundle-root> --output outputs\bundle_report.json
```

## What The Verifier Checks

- Counts files by extension.
- Lists Lean files, notebooks, and Python files.
- Strips Lean comments and flags live proof placeholders:
  - `sorry`
  - `admit`
  - `unsafe`
  - top-level `axiom`
- Optionally runs Python tests discovered under `test_*.py`.
- Optionally runs `lake build` for directories that contain `lakefile.lean`.

This is not a substitute for mathematical review. It is a receipt generator and hygiene gate.

## Current Local Baseline

Verified on 2026-07-09:

- `D:\GitHub\David-OS\api`: 63 passed.
- `D:\GitHub\David-OS\tests`: 4 passed.
- `Faith-Thru-Physics-Lean-4--main`: `lake build` completed successfully with warnings.
- `Lean-4-Proofs-main\theophysics-lean-verification-package\python`: 9 passed.
- Lean placeholder scans on the downloaded Lean packages found 0 live placeholders.

## Environment Note

Some Lake/mathlib builds failed on this Windows machine because mathlib checkout hit Windows path-length limits. Treat that as an environment blocker unless reproduced from a short path or after enabling Windows long paths.

The failure mode observed was:

```text
Filename too long
fatal: unable to checkout working tree
```

## How This Maps To The 141-Test Dashboard

The dashboard's 59 not-built/open items are not all unit tests. They split into three buckets:

- **Runnable now:** Python/API tests, notebook sanity checks, Lean placeholder hygiene, selected `lake build` receipts.
- **Formal proof build work:** Lean theorem packages, proof packet build status, no-placeholder scans.
- **Research-program tests:** electroweak unification, long-horizon cosmology, SPARC comparisons, hi_CLASS, and similar empirical/formal projects.

The right next move is to keep adding runnable receipts around each proof packet while keeping unsolved research tests labeled as open, not quietly pretending they are passed.
