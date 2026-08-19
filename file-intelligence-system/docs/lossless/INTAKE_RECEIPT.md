# Lossless Splitter Intake Receipt

Imported: 2026-08-14

## Canonical source choice

The following source pairs in `\\192.168.2.50\h_hp\Documents\FIreshoot` were
byte-for-byte identical. The non-`(1)` filenames were copied here as the
canonical documentation copies. No source file was altered or removed.

| Imported file | SHA-256 |
|---|---|
| `lossless_splitter.py` | `b088dadde20840e2e5c278c5b9ee11ea21f7be66da56fc3056a4868f22147afb` |
| `LOSSLESS_SPLITTER_README.md` | `bba9348b33ee3da850169a915ffe691dddf3bd3534562c51957d011d304ba902` |

## Role

This splitter is a deterministic L0/L1 preservation tool. It creates split
parts and manifests whose concatenation can be verified against the original
bytes. It does not replace the source corpus, make semantic truth decisions, or
authorize source modification.

It complements `fis_folder_memory.py`: folder memory is the linked registry
view; the splitter is the independently verifiable source-packet layer.
