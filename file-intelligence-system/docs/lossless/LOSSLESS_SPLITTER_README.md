# Lossless Splitter

This companion program adds **canonical naming + multi-file splitting** to the lossless workflow.

For each source file it:

- detects `N =`, `V =`, and `R =` from the formal/NABLA identity when present;
- otherwise uses the first Markdown H1, then the original filename;
- splits one large file into multiple exact chunks;
- can process an entire folder containing many files;
- names every output part from the detected identity;
- writes a per-source split manifest plus one corpus manifest;
- verifies that concatenating all parts recreates the original byte-for-byte.

For the Master Equation manifest, the naming logic is based on the identity structure in its NABLA block. The source defines `N = MASTER_EQUATION_CHI`, `V = CANONICAL_LOCAL_AND_INTEGRATED_FORM`, and `R = R3`.

## Recommended command

```powershell
python lossless_splitter.py `
  "O:\Theophysics_Master" `
  "O:\Theophysics_Split" `
  --mode smart `
  --heading-level 2 `
  --max-bytes 120000
```

Example generated names:

```text
MASTER_EQUATION_CHI__CANONICAL_LOCAL_AND_INTEGRATED_FORM__R3__P001-OF-017__PURPOSE.md
MASTER_EQUATION_CHI__CANONICAL_LOCAL_AND_INTEGRATED_FORM__R3__P002-OF-017__NABLA_ADDRESS.md
MASTER_EQUATION_CHI__CANONICAL_LOCAL_AND_INTEGRATED_FORM__R3__P003-OF-017__CORE_EQUATION.md
```

## Modes

- `heading`: split at Markdown headings.
- `size`: split near a maximum byte size.
- `smart`: split by headings first, then subdivide oversized sections.

## Lossless rule

```text
SHA256(chunk_001 + chunk_002 + ... + chunk_N)
==
SHA256(original)
```

## Pipeline

```text
SOURCE FILE(S)
    ↓
lossless_splitter.py
    ↓
CANONICALLY NAMED CHILD FILES
    ↓
lossless_packer.py
    ↓
LOSSLESS PACKETS
    ↓
semantic / AI compression
    ↓
cross-document synthesis
```
