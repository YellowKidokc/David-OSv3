> Current issuance profile: `registry.py` issues UUIDv7 and `SERIES.NN_Original-Title`. Dotted IDs and older envelopes remain readable as historical references; the versioned standards below are retained for compatibility. See [the architecture](../../ARCHITECTURE.md).

# identity

**The official registry is `D:\theophysics-data\registry\document_registry.sqlite`**, built by the crew on 2026-11-07:
36 documents, 47 versions, 141 artifacts and 4 relations. Its readable exports are in `D:\theophysics-data\registry\exports\`.
The official copy of the standard is in `AI-CREW\CANON_DECISIONS\DOCUMENT_IDENTITY_STANDARD_v1.0.md`.

David-OS apps **read** that registry. They never create a second one.

What this folder holds:
- `IDENTITY_LAYERS_STANDARD_v1.0.md`: canonical extensible identity/DUAL/derivative standard.
- `identity-envelope.v1.schema.json`: language-neutral contract for any number of identifier layers.
- `layers.py`: standard-library reference implementation for short/root/derived UUIDs and DUAL relations.
- `identity.py`: checks the ID format, the `::` artifact references and the sidecar safety rules. Apps use it before they suggest anything.
- `sidecar.v1.schema.json`: the three-address sidecar format.
- `registry.sql` and `registry_rulings.json`: **a proposal only, not a second registry.** They add protections that the official database doesn't have yet:
  - an `approvals` ledger that only accepts David's approvals (rule 5);
  - database rules that refuse to change an ID once assigned (rule 3), reuse a displaced ID (rule 4) or overwrite an artifact (rule 2).

  `build_registry()` is only for tests in a temporary folder. Adding these protections to the official registry is the crew's call, with David's OK.

All new apps should import `shared.identity` or validate against the JSON schema. Do not copy
the UUID/DUAL rules into each app. Mutable paper-strength assessments remain separate from identity.
