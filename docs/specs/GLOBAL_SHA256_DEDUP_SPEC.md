# Global SHA-256 Deduplication — Required Specification

Status: **DESIGN REQUIREMENT — NOT YET IMPLEMENTED**

The canonical requirement is a whole-tree, byte-exact scan. For every file under
one explicitly authorized root, stream the exact bytes through SHA-256 and group
all occurrences by the complete digest, regardless of filename or location:

```text
same SHA-256 = byte-identical file
different SHA-256 = not an exact duplicate
```

This is not folder-family comparison. Files in `v3`, `v4`, `v5`, snapshots,
imports, backups, and prior sort attempts must converge into the same group when
their hashes match, even when their names and parent folders differ.

## Required behavior

1. Recursively inventory the entire authorized root.
2. Record every path, relative path, byte size, timestamps, SHA-256, and status.
3. Group every successfully hashed occurrence globally by full SHA-256.
4. Emit a complete occurrence manifest, duplicate-group report, exception report,
   scan metadata, counts, and an output-manifest hash.
5. Never silently omit unreadable or changed-during-scan files.
6. Never silently cap production hashing. Any bounded preview must say
   `PARTIAL_SCAN` and cannot support cleanup decisions.

## Non-negotiable boundary

This capability is read-only and propose-only. Hash equality proves byte
identity, not permission to delete a path. Identical copies may be referenced,
operationally required, intentionally mirrored, or part of recovery history.

No scan may automatically delete, move, rename, overwrite, archive, canonize, or
select an authoritative keeper. A later cleanup worker requires a separately
reviewed approval plan, pre-action re-hashing and drift checks, quarantine or
recovery, and a durable receipt. Near-duplicate/version-family analysis remains a
separate layer and must not contaminate exact-hash groups.

## Minimum acceptance checks

- Same bytes under unrelated paths and different names group together.
- Cross-version and cross-snapshot copies group together.
- Same names with different bytes remain separate.
- Empty files group correctly without automatic deletion.
- Changed or unreadable files become visible exceptions.
- The scan mutates no source file or directory.

