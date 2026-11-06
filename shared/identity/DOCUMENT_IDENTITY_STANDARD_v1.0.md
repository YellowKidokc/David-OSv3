# Document Identity Standard v1.0

Theophysics Research Initiative, POF 2828 · 2026-11-07 · Authority: David Lowe
Contributors: Claude/Fable, Opus 5.5 (Antigravity/Jim)

**The one rule: every knowledge object gets ONE permanent identity. Everything else hangs off it.**

Machine-readable versions:
- `sidecar.v1.schema.json`: the three-address sidecar
- `registry.sql`: the database layout
- `registry_rulings.json`: the current series registry rulings
- `identity.py`: validators for IDs, artifact refs and sidecars, plus the safety rules

## 1. Document ID: `SERIES.POSITION.SLUG`
- **SERIES:** a 3–5 letter code from the series registry, such as MEQU, JREV, DLAY, LAND, ONES or DUAL.
- **POSITION:** two digits, stable within the series.
- **SLUG:** the shortest distinctive word from the title, in uppercase. It's permanent once assigned.

| Position | Meaning |
|---|---|
| 00 | series index or governing document |
| 01–79 | principal ordered works |
| 80–89 | companions, addenda, supplemental works |
| 90–94 | appendices and reference works |
| 95 | concordance |
| 96 | glossary |
| 97 | bibliography or source registry |
| 98 | governance and rulings |
| 99 | archive/supersession map |

Assignment: the registry issues IDs; they aren't re-derived later. **The namer PROPOSES; the registry ASSIGNS after David approves.**
Once assigned, an ID never changes. Renaming, moving, reformatting and revising don't change it.
Only identity displacement gets a new ID: the central claim changes materially, support becomes opposition, the governing model or equation is replaced, or one work splits into several.
Displacement is recorded as `OLD --SUPERSEDED_BY--> NEW` and `NEW --DERIVED_FROM--> OLD`.

## 2. Derived artifacts: `DOCUMENT_ID::role[::version-or-run]`
Example: `DLAY.05.WATER::classify.105::v2`, `DLAY.05.WATER::audit::2026-11-06`.

Role vocabulary: `source`, `source.markdown`, `source.html`, `html.blue`, `html.site`, `render.blue`,
`render.site`, `classify.104`, `classify.105`, `vector.chi`, `vector.namer`, `metadata.frontmatter`,
`metadata.sidecar`, `audit`, `audit.structural`, `audit.lawyer`, `extract.claims`, `extract.evidence`,
`receipt`, `receipt.processing`, `receipt.move`, `formal.lean`, `formal.lean_stub`, `formal.lean_result`.

## 3. Version identity
Each version records `document_id`, `version_number`, `content_sha256`, `created_at`, `supersedes_version` and `revision_status`.
The same `document_id` covers formatting, spelling, expansion, added evidence, path changes, and rewrites that keep the central claim.

## 4. The three-address sidecar
| Address | Answers | Effect |
|---|---|---|
| **physical** | WHERE it lives (one home) | the only address that can propose a move; `move_authorized` stays false until David approves |
| **canonical** | WHAT work it does in the argument (build, laws, epistemic roles, canon status) | links and database views, never copies |
| **navigation** | HOW someone finds it (series, subjects, people, worldviews, ten-law emphasis, chi, document type, lifecycle) | virtual views and search, never copies |

`canon_status` is one of NOT_EVALUATED, CANDIDATE, EVALUATED, ADMITTED, REJECTED, SUPERSEDED or WITHDRAWN. **Only David assigns ADMITTED.**

## 5. Database
Five tables: `documents`, `versions`, `artifacts`, `runs`, `series`. See `registry.sql`.

## 6. Current registry rulings
See `registry_rulings.json` (DLAY, JREV, MEQU, and the cross-series dependencies).
Known discrepancies are carried as notes: MEQU.07 isn't written yet, and the files for MEQU.08 and MEQU.09 give each other's law number.

## 7. Safety rules
1. Never infer ADMITTED. Only David assigns it.
2. Never overwrite an existing artifact. A change makes a new version with a new artifact_id.
3. Never change a document_id because the path changed.
4. Never reuse a document_id after a confirmed displacement.
5. Require the approval ledger before applying IDs to existing files.
6. Preserve old paths, hashes, names and lineage.
7. Make every change reversible.
8. Begin with sidecars. Don't rename source files until the system is proven.
9. The namer PROPOSES; the registry ASSIGNS.
10. Exports must be understandable without the database.
