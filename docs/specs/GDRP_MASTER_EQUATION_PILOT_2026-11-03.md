# GDRP Master Equation Read-Only Pilot — 2026-11-03

## Scope

- Corpus: `C:\Users\David\Documents\faiththruphysics.com\10_VAULTS\14_MASTER_EQUATION`
- Operation under test: conservative index-representative selection
- Real stop: eight different-content files named `GRACE.md` occupy different rebuild and formalization roles
- Adviser: local Ollama `deepseek-r1:latest` (8.2B, Q4_K_M)
- Mutation authority: none

## Expected behavior

The host must stop because a shared basename does not establish duplicate, revision, or keeper lineage. The recovery layer should create a bounded event and evidence packet, ask DeepSeek whether the artifacts are distinct roles or require more evidence, validate its answer, and preserve HOLD unless the answer is grounded and policy-valid.

## Attempts

| Attempt | Packet/transport | Result |
| --- | --- | --- |
| 1 | Ollama chat endpoint with full JSON Schema | HTTP 400; recorded `MODEL_FAILURE` |
| 2 | Generate endpoint, JSON mode, eight excerpts | Timed out after 300 seconds; HOLD preserved |
| 3 | Generate endpoint, JSON mode, four 700-character excerpts, thinking disabled, bounded output | Timed out after 120 seconds; HOLD preserved |
| 4 | Unloaded the lingering DeepSeek model, verified no model remained loaded, replayed the unchanged bounded packet | Timed out after 180 seconds; HOLD preserved |
| 5 | Existing configured DeepSeek API, same four-file bounded evidence packet | Returned structured assessment in about 7 seconds; first evaluator accepted it, but review found `safe_to_retry: true` contradicted its own statement that representative selection was not authorized |
| 6 | DeepSeek API with exact `retry_operation_id` contract and contradiction check | Passed; classified artifacts as distinct roles, set `safe_to_retry: false`, kept representative selection stopped, and proposed evidence collection |
| 7 | DeepSeek API with collaborator card and persistent working-note contract | First response exceeded the old token cap and produced a deterministic failure note; bounded replay with a larger response allowance passed and wrote a complete append-only adviser note |

## Result

The fail-safe behavior passed:

- the ambiguity remained stopped;
- no DeepSeek response was accepted;
- no correction or retry of the host operation was authorized;
- no Master Equation file was renamed, moved, deleted, or edited;
- every attempt produced a local diagnostic receipt under ignored `_data/recovery/` runtime storage.

The local adviser behavior failed:

- local DeepSeek did not return a schema-valid assessment within the allowed time;
- therefore the pilot did not demonstrate successful AI diagnosis or resolution;
- local Ollama DeepSeek must not yet be treated as a reliable recovery adviser for this packet size/runtime configuration.

The configured DeepSeek API adviser passed the corrected contract:

- it cited all four evidence records;
- it distinguished adjudication, bound-receipt, definition-audit, and integrated-atlas roles;
- it refused to infer duplicate or revision lineage from the shared basename;
- it returned notes and ratings for three corrections;
- it set `safe_to_retry: false` and `retry_operation_id: null` for the stopped representative-selection operation;
- it recommended collecting full files, manifests, provenance links, and folder-role documentation;
- it selected no filesystem keeper and proposed no corpus mutation.

The successful corrected API call used 2,141 prompt tokens and 1,125 completion tokens (3,266 total). This is one measured call, not a reliability statistic.

The notebook-enabled call additionally recorded the adviser's own concise situation summary, known facts, unknowns, assumptions, requested evidence, helpful tools, safest next step, cautions, and direct note to David. The note remained explicit that classification as distinct roles does not authorize retrying representative selection.

Post-test corpus observation remained 3,184 files and 212,113,554 bytes. The newest corpus write remained the pre-test `.obsidian\workspace.json` timestamp of 2026-11-03 10:52:44 local time.

## Supervisor decision

A launcher such as a `.bat` file may start the recovery service, but it must not own recovery decisions. A Python supervisor should:

1. preserve the host stop;
2. write the normalized event and evidence packet;
3. call the adviser with a deadline;
4. record transport, schema, timeout, and model errors separately;
5. check whether a timed-out local generation remains loaded/running;
6. reset only the adviser process/model when policy allows;
7. replay the identical packet at most once after reset;
8. stop retrying when no new evidence exists or the clean retry fails;
9. require a valid adviser response and policy evaluation before simulating any correction;
10. never restart or unblock the host operation merely because the adviser restarted.

## Next test

Before another corpus-level attempt, run a small adviser conformance test that measures:

- JSON response support;
- latency for 1 KB, 3 KB, and 8 KB packets;
- cancellation behavior after client timeout;
- whether `think: false` is honored by this model/build;
- maximum reliable response size;
- schema-valid response rate over a fixed test set.

The API path may proceed to additional read-only conformance cases. The local Ollama path still needs the adviser conformance test before another corpus-level attempt.

