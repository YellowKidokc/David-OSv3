# David-OS OrionBelt Integration

Status: `SPECIFICATION_ONLY`  
Authority: `READ_ONLY_PROJECTION`  
Pinned OrionBelt release: `v2.26.0`  
Pinned commit: `3a35445437deecb924fdb6eab28e6a8acefd935a`

## Purpose

This directory defines a replaceable, read-only connection from David-OS to
OrionBelt. OrionBelt may expose Canon data to dashboards, MCP clients, and
analytical queries. It is not the Canon Engine and cannot classify, admit,
correct, supersede, or mutate Canon objects.

The independently updateable OrionBelt checkout is located at:

```text
D:\GitHub\orionbelt-semantic-layer
```

## Authority boundary

```text
Canon Engine / canonical SQLite
        -> read-only projection
OrionBelt semantic model
        -> query surfaces
MCP / dashboards / spreadsheet views / AI collaborators
```

- Canon remains the only source of truth.
- Candidate and Admitted membership must remain distinguishable.
- `proof_label` is preserved without modification.
- `one_axiom_classification` remains an independent field.
- A semantic query cannot create a ruling or admission event.
- AI-generated descriptions and classifications remain proposals.
- The live Canon SQLite database is never used as an OrionBelt write target.

## Files

- `integration.json` — pinned paths, version, and safety settings.
- `canon_projection.mapping.yaml` — proposed semantic mapping; not yet an
  executable OBML model.
- `Test-OrionBeltIntegration.ps1` — read-only preflight and version check.

## Current state

The upstream source is cloned and pinned. No Python package, service, model,
MCP server, database driver, or scheduled process has been installed or
started. The projection remains blocked until the Canon query views and
read-only database copy/export contract receive an explicit ruling.

## License

OrionBelt v2.26.0 is distributed under Business Source License 1.1. Preserve
the upstream `LICENSE`. Review commercial embedding/service restrictions before
any public or commercial deployment.

