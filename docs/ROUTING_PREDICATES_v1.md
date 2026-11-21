# David-OS Routing Predicates v1

Every automated classifier is advisory. Before a classifier-generated move can execute, it must produce and pass a `david-os.routing-predicates.v1` receipt.

These are operational truth predicates: they establish facts about the proposed routing operation. They do **not** establish that the document's theological, scientific, historical, or philosophical claims are true.

| ID | Predicate | Required fact |
|---|---|---|
| RP01 | Title prominence | Filename and explicit title layers are recorded numerically: filename 12, frontmatter title 10, H1 8, other headings 4, body 1. |
| RP02 | Series integrity | Numbered/named siblings are inventoried. A series is moved as one reviewed set unless David explicitly approves a split. |
| RP03 | Folder context | The source neighbourhood and proposed destination neighbourhood are inspected before approval. |
| RP04 | Destination coherence | The target is a real, non-conflicting destination and batch routing remains coherent. |
| RP05 | Human approval | A model proposal is never sufficient authority to move a file. |
| RP06 | Reversibility | The operation has a receipt and undo path before execution. |
| RP07 | Decision concordance | The content/home signal and independent lineage/era signal agree; conflict, absence, or weakness produces HOLD. |

Each predicate returns `PASS`, `HOLD`, `FAIL`, or `NOT_APPLICABLE`. Any `HOLD` or `FAIL` blocks the routing move. The generic file-action worker enforces the receipt whenever a caller declares `routing_move: true`.

The classifier should still read the document. Prominence is weighting, not dictatorship: body content can overturn a misleading filename, but the conflict must be visible in the proposal rather than silently ignoring the title.

RP07 keeps two questions separate: where the material belongs by subject and
document function, and which generation it belongs to (current, prior, retired,
or system). For Master Equation material, lineage evidence is ranked: explicit
`supersedes` or canonical declarations, version family, internal document date,
filename/path date, hash-linked copies, then filesystem time. Filesystem time
alone cannot promote an old document into the current era.
