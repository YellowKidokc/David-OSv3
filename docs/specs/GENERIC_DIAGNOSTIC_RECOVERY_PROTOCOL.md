# Generic Diagnostic Recovery Protocol

Status: reusable design specification  
Short name: GDRP  
Scope: any program that can report an error code and an output, regardless of language, framework, or operating system.

## Core idea

A program does not need to understand AI or implement a recovery engine. It only needs to emit a small, stable event:

```json
{
  "program_id": "example.application",
  "operation_id": "import-records",
  "error_code": "IMPORT_17",
  "output": {
    "content_type": "text/plain",
    "data": "Column account_id was not found"
  }
}
```

GDRP combines that event with a registered program profile, safe context providers, historical outcomes, and an adviser such as DeepSeek. It produces notes, rated correction proposals, and—when the host supports it—a simulation. It does not require the application to surrender control of execution.

The generic loop is:

`PROGRAM STOP -> normalized event -> context envelope -> adviser -> proposals -> policy -> simulation -> approval -> execution -> verification -> measured outcome`

## What is universal and what is program-specific

### Universal core

The reusable engine owns:

- event normalization;
- secret redaction and size limits;
- program-profile lookup;
- context collection;
- adviser prompt construction and response validation;
- correction notes and ratings;
- proposal deduplication;
- policy routing;
- immutable ledgers;
- prediction/outcome comparison and calibration statistics.

### Program adapter

Each application supplies only the capabilities it has:

- `describe`: what the program and operation are intended to do;
- `context`: safe evidence relevant to an error;
- `simulate`: predict the effect of a proposed correction;
- `apply`: perform an approved correction;
- `verify`: determine the outcome;
- `rollback`: reverse an application when supported.

Only `describe` is required. A program with no mutation adapter still receives diagnosis, notes, ratings, and suggested manual steps.

## Integration levels

| Level | Host supplies | GDRP result |
| --- | --- | --- |
| 0: Report | error code and output | normalized incident and generic diagnosis |
| 1: Explain | program profile | program-aware diagnosis and correction notes |
| 2: Investigate | context providers | evidence-grounded diagnosis and bounded checks |
| 3: Simulate | simulation adapter | exact predicted change set and plan hash |
| 4: Execute | apply/verify/rollback adapters | approval-bound correction and measured outcome |

Applications can stop at any level. Higher levels are optional capabilities, not assumptions.

## Minimal API

Language-specific libraries should expose the conceptual equivalent of:

```python
recovery.report(
    program_id="example.application",
    operation_id="import-records",
    error_code="IMPORT_17",
    output="Column account_id was not found",
    run_id="optional-host-run-id",
    metadata={"input_schema_version": "4"},
)
```

For a process that cannot import a library, the same event may be sent through:

- a JSON file in an inbox directory;
- standard input/standard output;
- a local HTTP endpoint;
- a message queue;
- a command-line wrapper that captures exit code, stdout, and stderr.

The transport is replaceable. The event contract remains the same.

## Normalized recovery event

The event conforms to `docs/schemas/gdrp-recovery-event.schema.json`.

Required fields:

- protocol version;
- program ID;
- operation ID;
- error code;
- output envelope.

Optional fields include exit status, severity, run/correlation IDs, timestamps, host metadata, structured state, artifact identities, trace events, and an explicit safe-context reference.

### Error codes

GDRP treats the error code as an opaque string. It may be:

- a program code such as `ADMIT-203`;
- an exception class such as `FileNotFoundError`;
- an HTTP status such as `HTTP_429`;
- a process exit code such as `EXIT_2`;
- a generated fallback such as `UNCLASSIFIED_FAILURE`.

The adapter may provide a catalog entry explaining the code. Unknown codes remain valid and are diagnosed with lower evidence coverage.

### Output envelope

Output is not assumed to be text. The envelope contains:

- `content_type`;
- `data` for bounded inline text/JSON, or `artifact_ref` for external content;
- `sha256` when available;
- `truncated` and original byte count;
- redaction information;
- encoding when relevant.

Large, binary, private, or regulated outputs stay outside the prompt. The adviser receives metadata and explicitly permitted excerpts.

## Program profile

The profile conforms to `docs/schemas/gdrp-program-profile.schema.json`. It is the adviser's reusable understanding of a host program.

A profile defines:

- program purpose and version;
- operations and their intended outputs;
- invariants that must remain true;
- known error-code meanings;
- safe context providers;
- allowed proposal action types;
- forbidden actions;
- available adapter capabilities;
- verification tests;
- approval policy;
- data sensitivity and redaction rules.

Profiles are versioned and hashed. Every assessment records the exact profile hash used.

## Adapter contract

Adapters communicate through JSON requests and responses so the generic engine does not depend on the host language.

### `describe`

Input: program and operation IDs.  
Output: profile or a profile reference.

### `context`

Input: normalized event plus requested evidence IDs.  
Output: bounded evidence records with provenance, sensitivity, collection time, and hashes.

Context providers must be individually named and allowlisted. The adviser cannot invent and invoke arbitrary shell commands.

### `simulate`

Input: one policy-eligible correction proposal.  
Output:

- predicted changes;
- affected resources;
- preconditions;
- invariant checks;
- collision/conflict results;
- rollback availability;
- deterministic plan hash.

### `apply`

Input: approved plan hash and approval receipt.  
Output: execution receipt. The adapter must refuse stale or mismatched plans.

### `verify`

Input: execution receipt and original event.  
Output: `RESOLVED`, `PARTIAL`, `UNCHANGED`, `NEW_STOP`, `REGRESSION`, `REVERTED`, or `UNMEASURED`, with checks and evidence.

### `rollback`

Input: execution receipt.  
Output: rollback receipt and verification results.

## Adviser contract

DeepSeek is one adviser implementation. The protocol may also use another local or remote model. The adviser receives:

1. normalized event;
2. program profile;
3. bounded evidence;
4. prior attempts for this incident;
5. relevant historical outcomes;
6. explicit allowed and forbidden actions;
7. the correction-response schema.

It returns:

- diagnosis and causal chain;
- evidence references and assumptions;
- missing evidence;
- zero or more corrections;
- notes and ratings for every correction;
- predicted outcome and failure modes;
- human question when a decision cannot be inferred.
- an inspectable working note describing what it knows, does not know, needs, and recommends preserving for the next attempt.

The adviser proposes. The policy engine routes. The host program executes.

### Collaborator card

Each installation may supply a short operator collaborator card. It tells the adviser who is requesting help, how candid it may be, whether it may request tools or evidence, and which working norms matter. The card must never weaken the program policy or grant execution authority. It improves the conversation; it does not override the gate.

The card is versioned and hashed. Its hash is stored with every assessment so changes in adviser behavior can be traced to the context it received.

### Persistent incident notebook

Each incident owns an append-only `adviser-notes.jsonl`. Every adviser attempt appends one schema-valid record conforming to `docs/schemas/gdrp-adviser-note.schema.json`.

The notebook records:

- situation in the adviser's own words;
- known facts and cited evidence;
- unknowns;
- assumptions;
- requested evidence or access;
- tools/programs that would help;
- safest next step;
- cautions for another attempt;
- direct note to the operator.

The next attempt receives a bounded summary of prior notes and their outcomes. It must distinguish inherited notes from current evidence and may correct earlier notes without deleting them. Notes are not hidden chain-of-thought and should not request it; they are concise operational memory that David and future advisers can inspect.

## Generic correction actions

Actions use namespaced types and structured parameters. The universal vocabulary begins with:

- `observe.collect_evidence`;
- `runtime.retry`;
- `runtime.restart_component`;
- `configuration.propose_change`;
- `data.propose_transform`;
- `filesystem.propose_change`;
- `dependency.propose_change`;
- `code.propose_patch`;
- `workflow.request_human_decision`;
- `workflow.keep_stopped`.

An adapter explicitly declares which types it supports. Unsupported or unknown actions cannot be simulated or executed.

## Notes and ratings

Every correction retains the original prediction and records:

- what failed and the proposed cause;
- evidence used and missing;
- proposed correction and affected scope;
- expected result, side effects, and failure modes;
- verification and rollback method;
- diagnosis confidence;
- correction-success probability;
- no-regression probability;
- evidence coverage;
- assumption load;
- reproducibility probability;
- human-review need;
- impact and risk;
- rationale and evidence IDs for each rating.

After execution, the outcome is appended rather than rewriting the prediction.

Working notes are stored even when no correction is proposed. A timeout or malformed response receives a deterministic supervisor note stating what failed, which packet was used, and what the next attempt must know.

## Statistics

The core tracks predictions separately from measured outcomes. Statistics are grouped by:

- program and operation;
- error code/error family;
- adviser model and prompt version;
- program-profile version;
- correction action type;
- adapter version.

Each report shows sample size, successes, regressions, abstentions, Wilson 95% intervals, Brier score, calibration buckets, and false-safe count. Groups below 20 measured attempts are labeled `INSUFFICIENT_SAMPLE`.

Statistics may prioritize review or lower trust. They never override the host policy or authorize execution.

## Generic policy defaults

1. Missing profile: diagnose generically; do not execute.
2. Missing context: expose uncertainty; do not pretend the error code proves causation.
3. Invalid adviser output: record model failure; keep the host stopped.
4. Unknown action: reject it.
5. Mutation without simulation support: provide manual notes only.
6. Simulation without approval support: do not call `apply`.
7. Changed state after simulation: invalidate the plan.
8. Safety, privacy, legal, authority, or destructive ambiguity: require human review.
9. Repeated proposal without new evidence: stop the advisory loop.
10. The host's original stop condition remains authoritative until verification passes.

## Packaging recommendation

Implement the generic system as a small independent package, not inside a single application:

```text
gdrp/
  core/              event normalization, policy, ledger, statistics
  schemas/           stable protocol contracts
  advisers/          DeepSeek, Ollama, other providers
  transports/        file inbox, CLI, HTTP, queue
  adapters/          host-specific plugins
  profiles/          versioned program profiles
  reports/           human-readable correction review
  notebooks/         append-only per-incident adviser notes
```

David-OSv3, Python-WEB, CocoIndex, and other programs each receive their own adapter and profile. No host-specific rule belongs in the universal core.

## Conformance tests

A GDRP-compatible integration must demonstrate:

1. A program can submit only an error code and output.
2. Unknown error codes are accepted and remain appropriately uncertain.
3. Text, JSON, and external artifact outputs normalize safely.
4. Secrets and oversized output are not passed to the adviser.
5. The same event/profile/evidence produces a traceable assessment input hash.
6. Every correction includes notes, ratings, rationales, and evidence references.
7. Unsupported actions are rejected before simulation.
8. Apply refuses a missing, changed, or unapproved plan hash.
9. Verification preserves regressions and unresolved outcomes.
10. Statistics never count unmeasured or partial outcomes as successes.

