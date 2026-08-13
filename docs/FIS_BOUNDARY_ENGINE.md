# FIS Boundary Engine v0.1

The boundary engine is the mandatory checkpoint between a proposed file set and the executor.

```text
discover candidates
-> scan source records
-> verify the installed release manifest
-> simulate target paths
-> evaluate before-boundaries
-> write dry-run plan and boundary receipt
-> explicit approval
-> safety recheck
-> execute
-> evaluate after-boundaries
-> rollback on verification failure
-> append execution receipt
```

The executor cannot run unless the plan is `PASS`, has a nonempty approval ID, has
`dry_run=False`, and has not already executed. Direct deletion is not implemented.
`delete_later` means a governed move to a supplied quarantine path.
Immediately before execution, the orchestrator reruns preflight and verifies that
the approved source hashes have not changed.

## Dry-run example

```bash
python -m fis_boundary copy ./source.txt ./staging/source.txt
```

This command never mutates files. It prints the complete plan and writes it to the
SQLite ledger at `_fis_state/fis.sqlite`.

## Decision meanings

- `PASS`: every applicable boundary is known and passed.
- `FLAG`: read-only work may continue, but review is required.
- `BLOCK`: execution is forbidden.
- `UNKNOWN`: incomplete evidence; mutating operations convert this to `BLOCK`.

## Modules

- `scanner.py`: deterministic filesystem facts and hashes.
- `registry.py`: reusable boundary definitions and operation bindings.
- `boundaries.py`: three-valued condition evaluation.
- `planner.py`: dry-run action plans.
- `ledger.py`: canonical SQLite evidence trail.
- `executor.py`: the only module allowed to mutate files.
- `orchestrator.py`: the small public entrypoint connecting the stages.
