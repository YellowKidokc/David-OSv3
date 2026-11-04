# CocoIndex Admission and Lean 4 Tagging Architecture

**Status:** proposed design; no source-file mutation or automatic canon promotion  
**Home:** David-OSv3  
**Purpose:** make the first David-OS operations produce a trustworthy corpus that CocoIndex can incrementally index and tag for Lean 4 work.

## 1. The central decision

CocoIndex does not need the source folders to be physically cleaned, renamed, or rearranged before indexing. It needs a stable, reviewable admission contract.

The early pipeline should therefore organize **records before files**:

```text
Source folders
    -> OBSERVE: inventory, hashes, readability, protection
    -> RESOLVE: duplicate/version families and representative proposals
    -> ADMIT: READY / HOLD / EXCLUDE manifest
    -> COCOINDEX: extract, chunk, classify, tag, relate
    -> LEAN REVIEW: accept/correct formalization tags
    -> OPTIONAL CLEANUP: approved rename/move/quarantine plans
```

Physical sorting and naming no longer block CocoIndex. Later renames also do not create duplicate indexed documents because content identity is bound to SHA-256 rather than the current path.

## 2. Operations 1-3

### Operation 1: OBSERVE

Read sources in place and record:

- SHA-256 content identity
- every observed source path
- size, extension, timestamps and readability
- extraction result or explicit extraction failure
- protected root, project root, archive and generated-file signals
- scan/configuration version and receipt

This operation is read-only. It should reuse the Stage 1 registry and existing extractors rather than create a competing inventory.

### Operation 2: RESOLVE

Create reviewable structural relationships:

- exact duplicate: identical SHA-256
- normalized-text match: same readable text but different bytes
- probable version family
- unique readable artifact
- unreadable or unsupported artifact
- generated/cache/dependency material
- protected project or archive

The result is an **indexing representative**, not deletion authority. Every physical location remains attached to its content identity. A keeper cannot be selected by largest file, newest timestamp, shortest path or filename alone; authority, provenance, completeness, dependencies, editability and protected status all matter.

### Operation 3: ADMIT

Write a versioned admission manifest with three lanes:

| Lane | Meaning | CocoIndex behavior |
|---|---|---|
| `READY` | Stable, readable and permitted | Process normally |
| `HOLD` | Collision, uncertain version, protected material or review needed | Preserve record; do not semantically promote |
| `EXCLUDE` | Cache, generated output, dependency tree or known noise | Record exclusion reason; do not chunk/embed |

The admission decision must include rule IDs and evidence. `EXCLUDE` means excluded from this index pass, not deleted.

## 3. What “tag for Lean 4” means

There are three different tagging jobs. They must not be collapsed into one confidence score.

### A. Tags extracted from existing `.lean` files

These are deterministic observations:

- imports and namespaces
- declaration names and declaration kinds
- `theorem`, `lemma`, `def`, `structure`, `class`, `instance`, `axiom`
- active `sorry` count
- use of `native_decide`
- series classification from declaration content
- build receipt and `#print axioms` receipt, when available

The existing `LEAN 4/theophysics_corpus_indexer` parser and nomenclature remain the authority for these fields.

### B. Formalization-candidate tags for prose and research files

These tags say what a passage **might become** in Lean. They do not say it is true or proved.

Controlled values:

| Field | Allowed values |
|---|---|
| `claim_role` | `primitive`, `definition`, `conditional_theorem`, `bridge_claim`, `empirical_claim`, `historical_claim`, `open_conjecture`, `countermodel`, `objection`, `unknown` |
| `lean_readiness` | `not_applicable`, `needs_atomic_claim`, `needs_definitions`, `needs_premises`, `needs_types`, `needs_countermodel`, `ready_for_stub`, `existing_lean`, `compiled` |
| `formal_domain` | controlled namespaces such as `AXIOMS`, `MASTER_EQUATION`, `GRACE_COHERENCE`, `TEN_LAWS`, `TRINITY`, `HARNESS_TESTS`, or `UNCLASSIFIED` |
| `review_state` | `machine_proposed`, `human_accepted`, `human_corrected`, `rejected`, `superseded` |

The classifier should also extract candidate premises, conclusion, defined terms, quantifiers, dependencies and source spans. Every candidate must point back to exact text offsets in a content-hashed source.

### C. Verification tags

Verification is evidence-derived and separate from classification:

- `UNVERIFIED`
- `GAPS`
- `AI_REVIEW`
- `KERNEL_NATIVE_DECIDE`
- `KERNEL`

Only build and axiom-print receipts may raise a Lean artifact to a kernel verification level. A model classification, embedding similarity or high confidence can never do so.

## 4. Proposed record contract

Each admitted artifact should produce an artifact record and zero or more passage records.

```json
{
  "artifact_id": "sha256:<64 hex characters>",
  "source_sha256": "<64 hex characters>",
  "observed_paths": ["D:/.../source.md"],
  "admission": "READY",
  "admission_reasons": ["readable", "not_generated", "permitted_root"],
  "content_type": "markdown",
  "formal_domain": "AXIOMS",
  "claim_role": "conditional_theorem",
  "lean_readiness": "needs_premises",
  "source_span": {"start": 1024, "end": 1378},
  "candidate_premises": ["..."],
  "candidate_conclusion": "...",
  "dependencies": ["A0_IMAGO", "BC6"],
  "classifier": "lean-tag-contract-v1",
  "confidence": 0.78,
  "review_state": "machine_proposed",
  "verification": "UNVERIFIED"
}
```

Required invariants:

1. `artifact_id` is content-derived, never filename-derived.
2. Every interpretive tag has classifier/version, evidence span and confidence.
3. Missing and unknown remain null/unknown, never zero or false.
4. Machine proposals cannot change canon status, preferred version or human rulings.
5. A source hash change invalidates prior passage offsets and triggers reclassification.
6. Duplicate paths may share an artifact identity but retain separate location records.

## 5. CocoIndex pipeline

Use CocoIndex v1 processing components and target states:

```text
admission manifest
    -> mount_each(process_artifact, READY artifacts)
        -> verify current source hash
        -> extract text or parse Lean
        -> split into stable passages
        -> deterministic Lean syntax tags
        -> memoized formalization-candidate classifier
        -> declare artifact, passage, tag, relation and review rows
        -> declare review JSON/CSV sidecars in an owned output directory
```

Stable component keys should use the artifact hash and passage offsets, for example:

```python
coco.component_subpath("artifact", source_sha256)
coco.component_subpath("passage", source_sha256, start_offset, end_offset)
```

Expensive semantic classification should use `@coco.fn(memo=True)`. Updating one file then reprocesses only that artifact and its affected passages. The initial implementation should run in catch-up mode; live mode comes only after admission, deletion semantics and owned-output guards have acceptance tests.

## 6. Outputs

CocoIndex should own derived outputs outside source roots:

```text
_data/coco_lean/
    state/
    admission/
    tags.sqlite
    review/
        lean_candidates.jsonl
        lean_candidates.csv
        HOLD.md
    receipts/
```

Do not write tags directly into source Markdown, Obsidian frontmatter or `.lean` files in the first implementation. Export reviewable sidecars first. After David accepts or corrects a proposal, store that decision as a separate human-ruling row keyed by source hash and span.

## 7. Lean generation boundary

Tagging is not yet Lean code generation. A later, separately approved stage may create staging files such as:

```lean
namespace Proposed

-- Source: sha256:... span 1024:1378
-- Machine-proposed role: conditional_theorem
-- Missing premises remain explicit.
theorem candidate_name
    (h1 : PremiseOne)
    (h2 : PremiseTwo) : ProposedConclusion := by
  sorry

end Proposed
```

Generated stubs belong in a staging namespace and remain `GAPS` while `sorry` is active. Compilation proves only that the encoded statement/typechecks or theorem follows from its stated premises. It does not establish that the premises describe physics, theology, history or reality.

## 8. Review workflow

The review screen should show:

- exact source passage
- source hash and all observed paths
- proposed role/domain/readiness tags
- extracted premises and conclusion
- related existing Lean declarations
- duplicate/version context
- confidence and classifier version
- accept, correct, reject and defer controls

Accepted corrections become training/ranking evidence but never authorize file mutation or canon promotion.

## 9. Implementation order

1. Define and schema-validate `admission-v1.jsonl`.
2. Export it from the existing Stage 1 registry and duplicate/version evidence.
3. Build CocoIndex artifact/passages tables using deterministic extraction only.
4. Integrate the existing Lean parser and current nomenclature.
5. Add rule-based prose candidate tags with source spans.
6. Add a bounded model classifier only for unresolved candidates.
7. Build the human review queue and ruling ledger.
8. Add staged Lean stub generation behind explicit approval.
9. Compile staged files and store build/axiom-print receipts separately.
10. Consider live mode only after unchanged-run stability, changed-hash invalidation, missing-input, duplicate-path and owned-output tests pass.

## 10. Definition of done for the first milestone

The first milestone is complete when:

- sources remain byte-for-byte untouched;
- every processed artifact has a SHA-256 identity and admission ruling;
- exact duplicates share content identity without losing their paths;
- existing `.lean` syntax tags agree with the current parser;
- prose tags include exact evidence spans and remain machine proposals;
- verification and semantic classification are stored separately;
- changed source bytes invalidate stale passage tags;
- a second unchanged run produces byte-stable derived outputs;
- no tag changes canon status or triggers a rename/move/delete.

## 11. Existing components to reuse

- `engine.registry`: observation, permanent work/version identities and review queue
- `engine.fingerprint` and existing SHA-256 routines: content identity
- `engine.text_extractor`: bounded source extraction
- `LEAN 4/theophysics_corpus_indexer/lean_parser.py`: Lean declarations/imports/`sorry`
- `LEAN 4/theophysics_corpus_indexer/classifier.py`: content-derived series classification
- `LEAN 4/theophysics_corpus_indexer/NOMENCLATURE.md`: controlled codes and verification meanings
- FIS: advisory classification, protection and review evidence
- CocoIndex: incremental orchestration, memoization and declared derived targets

The goal is one joined pipeline, not another independent classifier.
