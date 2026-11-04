# David-OSv3 Diagnostic Recovery Loop

Status: design specification  
Authority: advisory diagnosis only; existing gates, admission decisions, simulation hashes, and human approvals remain authoritative.

## Purpose

When an operation stops, David-OSv3 must preserve the stop and produce enough structured evidence for DeepSeek to diagnose the obstruction, propose bounded corrections, and predict what each correction would change. DeepSeek never edits files, changes an admission lane, approves a rename, or converts uncertainty into permission.

The loop is:

`STOP -> failure capsule -> DeepSeek assessment -> correction proposals -> deterministic checks -> new simulation -> approval -> apply -> outcome measurement`

An error code is a routing label. The failure capsule is the evidence DeepSeek reasons from.

## Components

1. **Stop emitter**
   - Converts an exception, gate refusal, failed invariant, ambiguous decision, or exhausted retry into a failure capsule.
   - Captures the last successful step and exact stopping condition.
   - Redacts secrets and bounds excerpts before model use.

2. **System card registry**
   - Gives DeepSeek the operation's purpose, inputs, outputs, invariants, allowed actions, forbidden actions, and relevant code excerpts.
   - Cards are versioned and hashed. The assessment records the card hash.

3. **Diagnostic adviser**
   - Sends the capsule and system card to a configured DeepSeek endpoint.
   - Requires schema-valid JSON.
   - May propose read-only checks or a registered repair. It cannot execute either.

4. **Correction evaluator**
   - Runs deterministic eligibility and safety checks on every proposal.
   - Rejects unknown actions, unbounded searches, mutation disguised as diagnosis, and claims unsupported by capsule evidence.

5. **Simulation binder**
   - Converts an eligible proposal into a normal David-OSv3 simulation.
   - Execution requires approval of the exact plan hash.
   - Any relevant state change invalidates the approval.

6. **Outcome recorder**
   - Re-runs the stopped operation after an approved correction.
   - Records success, partial success, unchanged failure, regression, and any new stop code.
   - Updates empirical performance statistics without allowing those statistics to grant mutation authority.

## Stop classes

| Class | Meaning | Default route |
| --- | --- | --- |
| `TRANSIENT` | Timeout, temporary lock, unavailable service | bounded deterministic retry |
| `DETERMINISTIC_DEFECT` | Known malformed state with registered repair | simulate registered repair |
| `MISSING_EVIDENCE` | More read-only evidence may resolve the decision | propose evidence checks |
| `AMBIGUOUS_AUTHORITY` | Canon, provenance, lineage, or ownership conflict | HOLD and ask David |
| `SAFETY_BOUNDARY` | Protected root, privacy, legal, unresolved references | HOLD; never bypass |
| `MODEL_FAILURE` | Invalid, unsupported, or ungrounded model response | record and stop advisory loop |
| `UNKNOWN` | No reliable classification | HOLD |

## Failure capsule

Every stop produces a JSON document conforming to `docs/schemas/failure-capsule.schema.json`. Required evidence includes:

- stable `failure_id`, `run_id`, and `error_code`;
- operation name, version, purpose, and stage;
- expected state and observed state;
- last successful step and execution trace;
- exception type/message when applicable;
- input identities and SHA-256 values, not unrestricted content;
- admission lane, family, gate verdict, and simulation hash when applicable;
- relevant rules and invariants;
- completed checks and their results;
- missing evidence;
- allowed and forbidden next actions;
- bounded excerpts, with source path and line/span provenance;
- environment versions needed to reproduce the stop;
- redaction record and capsule SHA-256.

The capsule must never contain API keys, passwords, tokens, private keys, browser storage, or unrestricted personal content.

## DeepSeek response

DeepSeek returns one assessment with zero or more correction proposals. Each proposal must include:

- `correction_id`;
- diagnosis and causal chain;
- evidence used, evidence not used, and assumptions;
- proposed action and exact bounded scope;
- expected result;
- predicted side effects and failure modes;
- prerequisites and verification checks;
- rollback or non-mutation statement;
- whether David must answer a question;
- a correction note suitable for the permanent ledger;
- ratings defined below.

Free-form advice outside the schema is retained as raw model output but is not eligible for simulation.

## Notes required for every correction

Every correction ledger entry must answer:

1. What stopped?
2. Why does DeepSeek think it stopped?
3. What evidence supports that diagnosis?
4. What remains uncertain?
5. What correction is proposed?
6. What exact files, records, or services would be affected?
7. What should change if the correction is right?
8. What could go wrong?
9. How will success and regression be tested?
10. Was it simulated, approved, applied, reverted, or rejected?
11. What actually happened afterward?
12. What did the system learn for the next occurrence?

Notes are append-only. Later results may supersede a note but never rewrite its original prediction.

## Ratings for every correction

All rating values are probabilities from `0.0` to `1.0` except impact and risk, which use the stated ordinal scale. A model rating is a prediction, not proof.

| Field | Meaning |
| --- | --- |
| `diagnosis_confidence` | Probability that the stated causal diagnosis is correct |
| `correction_success_probability` | Probability that the proposed correction resolves this stop without another correction |
| `no_regression_probability` | Probability that defined invariants and existing tests remain satisfied |
| `evidence_coverage` | Fraction of material claims linked to capsule evidence |
| `assumption_load` | Fraction of material reasoning steps dependent on unverified assumptions; lower is better |
| `reproducibility_probability` | Probability another run from the same captured state reproduces the diagnosis/result |
| `human_review_need` | Probability that a human ruling is necessary even if technical checks pass |
| `impact` | `1` cosmetic, `2` local metadata, `3` local behavior, `4` multi-record/filesystem, `5` authority/canon/destructive boundary |
| `risk` | `1` negligible, `2` low, `3` moderate, `4` high, `5` prohibited without explicit exceptional authority |

DeepSeek must provide a short rationale and cited evidence IDs for every rating. The system rejects missing rationales, impossible probabilities, or a high-confidence proposal whose evidence coverage is below the configured floor.

## Statistical measurement

Do not present model confidence as an observed success rate. Store three layers separately:

1. **Prediction** — DeepSeek's probability at proposal time.
2. **Outcome** — deterministic result after an approved attempt.
3. **Calibration** — historical comparison of predictions with outcomes.

For each model, prompt version, stop class, error code, and correction type, track:

- attempts and eligible attempts;
- approved, rejected, applied, reverted, and unresolved counts;
- resolution rate with numerator, denominator, and Wilson 95% interval;
- regression rate with numerator, denominator, and Wilson 95% interval;
- mean Brier score for binary predictions;
- calibration buckets: `0-.2`, `.2-.4`, `.4-.6`, `.6-.8`, `.8-1.0`;
- mean absolute calibration error, weighted by bucket count;
- false-safe count: predicted safe but produced a regression or violated an invariant;
- abstention/HOLD rate;
- median attempts and elapsed time to resolution.

Until a group has at least 20 measured attempts, label its rate `INSUFFICIENT_SAMPLE` and always show `n`. Do not create fake precision from small samples. Historical performance can rank proposals or request extra review; it cannot authorize mutation.

### Outcome labels

- `RESOLVED`: original stop is gone and all required checks pass.
- `PARTIAL`: measurable progress, but the operation remains stopped.
- `UNCHANGED`: same stop remains.
- `NEW_STOP`: original stop cleared but another stop prevents completion.
- `REGRESSION`: an existing invariant/test fails or protected state changed unexpectedly.
- `REVERTED`: apply was reversed successfully.
- `UNMEASURED`: no approved application or verification result exists.

## Decision policy

The deterministic policy engine, not DeepSeek, assigns the route:

| Condition | Route |
| --- | --- |
| Schema invalid or evidence references missing | `MODEL_FAILURE` |
| Proposed action is forbidden | reject proposal and preserve HOLD |
| Risk 4-5, authority ambiguity, canon decision, or filesystem keeper | David review required |
| Any proposed mutation | simulation and exact plan approval required |
| Read-only bounded evidence request | may run automatically if permitted by operation policy |
| Registered idempotent transient retry | may retry within configured count/time budget |
| Retry budget exhausted or state changed | new capsule and HOLD |

No score threshold may override a gate, admission lane, protected root, legal/privacy boundary, unresolved reference, or human ruling.

## Loop limits

- Maximum two DeepSeek advisory rounds per failure by default.
- Maximum three deterministic transient retries.
- No recursive model-to-model conversations without a new evidence-bearing capsule.
- Stop when no new evidence is added between rounds.
- Stop when proposals repeat, conflict, exceed scope, or lower evidence coverage.
- Preserve unrelated work: one held item does not block independent READY items.

## Storage

Suggested registry tables:

- `failure_events`
- `diagnostic_assessments`
- `correction_proposals`
- `correction_notes`
- `correction_outcomes`
- `model_calibration`

Raw capsules and responses are immutable JSON under `_data/recovery/<run_id>/`. SQLite stores identities, hashes, normalized fields, decisions, and links to those artifacts.

## Initial implementation boundary

Phase 1 should support diagnosis and simulation only:

1. emit failure capsules from Stage 2A and Stage 2B stops;
2. build versioned system cards for ADMIT, sidecar generation, and rename simulation;
3. call local Ollama DeepSeek or a configured DeepSeek API through one bounded adapter;
4. validate and ledger every assessment/correction;
5. generate correction simulations and review reports;
6. record human decisions and later outcomes;
7. calculate calibration statistics only from measured outcomes.

Phase 1 must not add autonomous correction application.

## Acceptance tests

1. An unknown stop creates a complete capsule and remains HOLD.
2. Secrets in exception text or environment data are redacted before persistence/model use.
3. Invalid DeepSeek JSON produces `MODEL_FAILURE` and no simulation.
4. Every correction has notes, ratings, rationales, and evidence links.
5. A forbidden action is rejected regardless of confidence.
6. A changed source, sidecar, admission decision, or target invalidates the simulation.
7. Applying an approved correction records an immutable pre-apply prediction and post-apply outcome.
8. Statistics expose numerator, denominator, interval, and sample sufficiency.
9. A regression is visible and cannot be counted as success.
10. Repeated advice without new evidence stops the loop.

