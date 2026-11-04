# David-OSv3 Stage 2A Build Prompt: Admission Manifest

## Mission

Implement the missing **Operation 3: ADMIT** component in `D:\GitHub\David-OSv3`.

Stage 2A consumes existing observation and resolution evidence and emits a deterministic, schema-validated admission manifest for CocoIndex. It must not rename, move, delete, quarantine, canonize, or edit any source file.

This is a prerequisite contract for CocoIndex and for the existing Stage 2B sidecar/ME/rename work. Stage 2B may mirror admission fields into `.fis.json`; it must not independently assign or override admission decisions.

## Existing components to reuse

Do not replace these systems:

- `engine/inventory_scan.py`: inventory observations
- `engine/fingerprint.py`: SHA-256/content identity evidence
- `engine/registry.py`: persistent works, versions, paths and review history
- `engine/canon_sidecar.py`: duplicate/version-family adaptation
- existing protection, project-root and generated-file signals
- existing SQLite registry and review queues

Inspect their live schemas and interfaces before writing adapters. Do not infer that a planner, catalog or report is an executor.

## Required deliverables

1. `docs/schemas/admission-manifest-v1.schema.json`
2. An admission module under `engine/` with a narrow CLI entry point
3. Deterministic JSONL output at `_data/admission/admission-v1.jsonl`
4. A human-readable review report at `_data/admission/ADMISSION_REVIEW.md`
5. A run receipt at `_data/admission/receipts/<run-id>.json`
6. Focused tests covering lane assignment, representative selection, conflicts and byte stability
7. Documentation showing the exact command and input/output ownership

Generated outputs belong under `_data/admission/`. Never place them in scanned source roots.

## Manifest contract

Every observed artifact/location must remain represented. Required fields:

```json
{
  "schema_version": "admission-manifest/v1",
  "artifact_id": "sha256:<64 lowercase hex characters>",
  "source_sha256": "<64 lowercase hex characters>",
  "observed_paths": ["D:/absolute/source/path.md"],
  "family_id": "vf:<stable family identifier or null>",
  "family_relation": "exact_duplicate | normalized_text_match | probable_version | unique | unresolved",
  "lane": "READY | HOLD | EXCLUDE",
  "reason_codes": ["CONTROLLED_CODE"],
  "representative_sha256": "<64 lowercase hex characters or null>",
  "representative_scope": "index_only | none",
  "decision_authority": "deterministic_rule | human_ruling | unresolved",
  "decision_version": "admission-rules/v1",
  "evidence": [],
  "source_registry_version": "<receipt or transaction identity>",
  "decided_at": "<receipt timestamp>"
}
```

The serializer must use a stable record order and stable key order. Volatile timestamps belong in the receipt, not in otherwise byte-stable unchanged manifest rows. If `decided_at` prevents byte stability, keep it only in the run receipt and store a stable decision/ruling identifier in each row.

## Lane rules

### READY

Assign `READY` only when all required conditions are satisfied:

- the current bytes match `source_sha256`;
- at least one readable/permitted location exists;
- the artifact is not generated/cache/dependency noise under configured rules;
- no hard safety boundary is unresolved;
- duplicate/version-family handling has either selected an index representative or established that the artifact is independently indexable;
- no unresolved human ruling conflicts with the result.

### HOLD

`HOLD` is the fail-safe lane. Use it for:

- protected or project-root ambiguity;
- conflicting human rulings;
- unresolved references/dependencies that could make representative selection unsafe;
- probable versions with no defensible preferred/index representative;
- unreadable extraction where semantic processing is required;
- content/hash drift between registry evidence and current bytes;
- incomplete provenance or authority conflict;
- malformed or missing required input evidence;
- any unknown condition that affects admission safety.

### EXCLUDE

Use `EXCLUDE` only for a configured, evidence-backed indexing exclusion such as:

- build/cache/dependency/generated output;
- unsupported material explicitly outside this CocoIndex corpus;
- exact duplicate location whose content is represented by the same SHA-256 artifact record.

`EXCLUDE` means excluded from this indexing pass. It is never deletion authority. Preserve the path, reason and content identity.

## Two separate decisions

Never conflate:

1. **Index representative**: which content CocoIndex processes to avoid redundant work.
2. **Filesystem keeper**: which physical file may eventually survive cleanup.

Stage 2A may select only an `index_only` representative. It must not select or encode a filesystem keeper. Filesystem cleanup remains separately reviewed and approval-bound.

Exact byte duplicates share a content identity, so CocoIndex may process the bytes once while retaining every path. Non-identical version-family members are not duplicates and must not be silently collapsed.

## Representative decision matrix

Evaluate criteria in this order. A higher row dominates lower rows. Do not convert the rows into an opaque blended score.

| Priority | Criterion | Decision effect |
|---:|---|---|
| 1 | Hard safety boundary | Force `HOLD`; protection does not itself make a file representative |
| 2 | Explicit human ruling | An applicable, source-bound preferred-version ruling wins |
| 3 | Provenance and authority | Prefer controlled original, signed/exported canonical source or documented lineage |
| 4 | Dependency/reference integrity | Prefer the artifact referenced by code, indexes, citations, manifests or published outputs |
| 5 | Completeness/content integrity | Prefer complete, non-truncated and non-corrupt content |
| 6 | Editability/source quality | Prefer native source over flattened PDF, screenshot, OCR or derived export |
| 7 | Recency with revision evidence | Newer wins only when evidence establishes it as a revision |
| 8 | Location/name quality | Presentation hint only; never authority |
| 9 | Size | Final tie-breaker only; never a primary rule |

If a protected project copy is less complete than a scratch copy, retain both and assign the family `HOLD` unless lineage or a human ruling resolves the relationship. Do not let either protection or completeness alone manufacture a winner.

## Reason-code registry

Define controlled reason codes, document them and reject unknown codes. At minimum include:

```text
READY_READABLE_PERMITTED
READY_EXACT_CONTENT_REPRESENTATIVE
HOLD_PROTECTED_AMBIGUITY
HOLD_PROJECT_ROOT_AMBIGUITY
HOLD_VERSION_UNRESOLVED
HOLD_HUMAN_RULING_CONFLICT
HOLD_REFERENCE_RISK
HOLD_HASH_DRIFT
HOLD_UNREADABLE
HOLD_INPUT_INCOMPLETE
EXCLUDE_EXACT_DUPLICATE_LOCATION
EXCLUDE_GENERATED
EXCLUDE_CACHE
EXCLUDE_DEPENDENCY
EXCLUDE_OUT_OF_SCOPE
```

Store evidence for every reason: rule ID, input record identity and relevant path/hash/ruling reference.

## Stage 2B consumption contract

The existing sidecar writer may add this read-only block to `.fis.json`:

```json
{
  "admission": {
    "schema_version": "admission-manifest/v1",
    "lane": "READY",
    "reason_codes": ["READY_READABLE_PERMITTED"],
    "representative_sha256": "...",
    "family_id": "...",
    "decision_authority": "deterministic_rule",
    "decision_version": "admission-rules/v1"
  }
}
```

Stage 2B must copy this block from a matching source-hash-bound manifest row. If the hash is absent, stale, contradictory or ambiguous, it must emit/retain `HOLD`; it may not recompute `READY` locally.

The ME bridge and rename-review components remain downstream. Admission never changes ME status, preferred version, canon status or rename approval.

## CLI behavior

Provide explicit commands equivalent to:

```powershell
python -m engine.admission build --db _data/registry.sqlite --output _data/admission/admission-v1.jsonl
python -m engine.admission validate --manifest _data/admission/admission-v1.jsonl
python -m engine.admission explain --sha256 <hash>
```

`build` and `validate` are read-only with respect to source roots. `explain` must show the ordered criteria, winning/holding rule and evidence; do not expose only a final score.

## CocoIndex handoff

CocoIndex consumes only schema-valid rows. Its first implementation should:

- process `READY` artifacts;
- record but not semantically promote `HOLD` artifacts;
- retain exclusion metadata for `EXCLUDE` artifacts;
- use `source_sha256` as the stable artifact component identity;
- verify live bytes against the admitted hash before extraction;
- stop or hold the artifact on hash drift;
- never infer deletion when a row disappears without a complete successful source observation.

Use CocoIndex v1 APIs (`coco.App`, `@coco.fn`, `mount_each`, declared target states). Do not use removed v0 flow APIs.

## Acceptance tests

At minimum prove:

1. An unchanged second run produces byte-identical manifest and review outputs.
2. Exact duplicate paths share one content identity and retain all locations.
3. A probable-version family without a ruling becomes `HOLD`.
4. A valid source-bound human preferred-version ruling outranks lower criteria.
5. Protected ambiguity becomes `HOLD`, not automatic representative selection.
6. A more complete scratch copy does not automatically defeat a protected project copy.
7. Size cannot defeat provenance, dependency, completeness or editability evidence.
8. Hash drift between registry and live source becomes `HOLD`.
9. Unknown reason codes and malformed rows fail schema validation.
10. Partial traversal/input failure cannot produce false `EXCLUDE` or missing-file conclusions.
11. No source file is created, modified, moved, renamed, quarantined or deleted.
12. Stage 2B refuses to mirror a stale or mismatched admission block as `READY`.

## Non-goals

- No physical cleanup or survivor selection
- No rename application
- No source-side sidecar creation
- No canon or lifecycle promotion
- No semantic Lean tagging
- No embeddings or graph construction
- No live/watch mode
- No automatic learning that changes lane authority

Stage 2A is complete when it produces a deterministic, explainable, source-hash-bound contract that CocoIndex and Stage 2B can consume without acquiring new mutation or canon authority.
