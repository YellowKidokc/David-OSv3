# FIS Folder Memory v2

`fis_folder_memory.py` creates the navigable folder-memory layer. It is an
inventory rail, not a cleanup rail: it never moves, renames, deletes, or
promotes files.

## Authority

1. `fis_folder_memory.sqlite` is the canonical registry.
2. A folder's `.fisnote` is a generated, human-readable view of its direct
   contents plus links to its child folders.
3. A file is described in the registry once and listed in the `.fisnote` of
   the folder where it lives. References elsewhere are links, never copied
   descriptions.
4. Unknown semantic fields remain `UNRESOLVED` or `unclassified` until an NLP
   receipt or human decision supplies them.

## Compact note shape

Each generated note contains:

| Section | Purpose |
|---|---|
| Hidden `fis:meta` block | Stable IDs and machine fields for tools. |
| Summary row | Type, state, file count, format counts, health, scan time. |
| Files here | Direct files only, each with a relative link and parseable ID/hash. |
| Child folders | Direct children only, each linked to its own `.fisnote`. |
| Open context | Honest unresolved fields and registry lookup directions. |

## Registry fields

Folder records carry: identity, path, purpose, folder type, domain, series,
chain steps, status, owner, canonical-source flag, parent backbone, counts,
created time, scan time, and notes.

File records carry: identity, living folder, type/format, domain/series/chain,
reading level, presentation markers, canonical/superseded status, content hash,
truth-node count, lifecycle status, modification time, size, and scan time.

`purpose`, `domain`, `series`, `chain_steps`, `owner`, canon status, and
reading level are intentionally not guessed from a filename.

## Safe commands

Registry-only scan of one folder:

```powershell
python .\fis_folder_memory.py "D:\path\to\folder" --db .\fis_folder_memory.sqlite
```

Inventory a tree without creating notes:

```powershell
python .\fis_folder_memory.py "D:\path\to\folder" --tree --db .\fis_folder_memory.sqlite
```

Write generated views only after reviewing the registry:

```powershell
python .\fis_folder_memory.py "D:\path\to\folder" --tree --write --db .\fis_folder_memory.sqlite
```

On an explicit `--write`, an existing `.fisnote` is copied first to
`.fisnote.legacy.YYYYMMDD_HHMMSS`. Nothing is deleted.

## Next integration

After a content-folder pilot, this generator can become the writer called by
`fis_folder_daemon.py`. That is deliberately deferred: the existing daemon is
live legacy behavior and should not be silently replaced during a schema change.
