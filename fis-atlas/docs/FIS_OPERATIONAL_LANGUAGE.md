# FIS Operational Language (the shared codebook)

A short character string does not *contain* "move", the full drive path, the
policy, and 200 filenames. It contains **stable references** to definitions in a
shared registry — exactly like language: the letters don't hold their meaning, a
shared dictionary does. Because both sides possess the evolving dictionary, 24
characters can reference and *explain* an enormous amount of operational history.

This is **not primarily compression**. It is a language:

```
Objects + operations + locations + policies + decisions + results
```

## The registry (permanent repository of shortcuts)

Codes exist for: drives/roots, folders/paths, operations, file-sets/manifests,
classifications, policies/permissions, customer decisions, organization
strategies, results/verification states, time periods, jobs/workflows.

```yaml
operations: { L: scan, I: identify_and_hash, U: classify, S: compare_and_cluster,
              C: copy, M: move, R: rename, A: archive, Q: quarantine,
              D: deduplicate_in_collection, V: verify, G: generate_report }
roots:      { "01": C:/Research, "02": D:/Old Research, "03": O:/Theophysics,
              "04": //192.168.2.50/h_hp/Desktop, "05": O:/GTQ_AGGREGATE }
strategies: { "01": flat, "02": by_extension, "03": semantic_categories,
              "04": series_then_format, "05": preserve_existing_structure }
policies:   { "01": observe_only, "02": copy_preserve_originals,
              "03": move_after_approval, "04": exact_dedupe_inside_aggregate,
              "05": archive_after_approval, "06": protected_research_corpus }
results:    { "00": proposed, "01": approved, "02": partially_completed,
              "03": completed_and_verified, "04": blocked, "05": rolled_back }
```

`M 02 05 03` = MOVE from `D:/Old Research` to `O:/GTQ_AGGREGATE` under
move-after-approval.

## File-sets & manifests

A set of 200 files is named once; the manifest supplies the exact objects (and
is **hashed** so nobody can silently change which 200 files it means).

```yaml
sets:
  G7K4: { name: GTQ confirmed set, object_count: 200,
          membership_manifest: manifests/G7K4.fism, membership_rule: GTQ-RULE-04,
          manifest_hash: "82d4..." }
```

`M:G7K4:02>05:P03` = move the 200 files of set G7K4 from root 02 to root 05
under policy 03.

## Workflows & decisions as codes

```yaml
workflows:
  W7: { name: Verified corpus aggregation,
        sequence: [L, I, U, D, C, {organization: "04"}, V] }
decisions:
  D14: { question: Which format governs?, ruling: {editable_source: .md,
         derivatives: [.html, .pdf, .docx]}, scope: Genesis to Quantum,
         ruled_by: David Lowe }
```

## The 24-character capsule (fixed positions)

| Positions | Meaning |
|---:|---|
| 1 | schema version |
| 2–5 | node / collection id |
| 6–9 | set / manifest id |
| 10 | operation |
| 11–12 | source-root code |
| 13–14 | destination-root code |
| 15–17 | policy code |
| 18–19 | time-window code |
| 20–21 | result code |
| 22–24 | integrity check |

The readable statement form:

```
F2 W7 G7K4 01,02,03,04>05 O4 P2 D14 V3
```
> Under schema 2, run verified-aggregation workflow W7 on set G7K4, collecting
> roots 01–04 into 05, organizing series-then-format, preserving originals,
> applying ruling D14, result completed-and-verified.

## Non-negotiable registry rules

1. **Never reuse a code.** If `03` meant `O:/Theophysics`, it never means anything else.
2. **Version the registry.** Every capsule starts with its schema version.
3. **Supersede, never overwrite.** `P03: {status: superseded, replaced_by: P11}`.
4. **Hash every manifest.** Otherwise the set's meaning can be silently changed.
5. **Keep the registry recoverable beside the ledger.**
6. **Every code is decompressible.** The system must produce plain English on demand.

## Where it lives

YAML in `fis-registry/` is the **readable source of truth**; SQLite is the
**compiled index** for fast lookup. Every folder's `.fisnote` carries a capsule
at the bottom recording its operational history — decompressible via the registry.
