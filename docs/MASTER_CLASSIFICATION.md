# Master Classification Intake

Desktop and Documents are intended master intake roots. The service observes
new and changed files, records identity and local classification, and escalates
only uncertain classifications to DeepSeek. It never moves or renames a source
file merely because a classifier is confident.

## Three confidence bands

1. **Carry cleanly** — a local or DeepSeek result at or above `0.90` continues
   into classification metadata, sidecars, SQLite and downstream FIS views.
2. **Carry provisionally and notify** — a DeepSeek result from `0.60` through
   `0.899...` continues with a provisional flag and creates a Notification Hub
   item for David.
3. **Hold and notify** — a missing label, a DeepSeek result below `0.60`, or
   `needs_human=true` does not continue into settled downstream classification.

Thresholds and roots live in `config/master_classification.json`. The pure
decision boundary is `engine/classification_policy.py`. Live DeepSeek calls,
background enrollment and Notification Hub delivery must use these decisions
but remain disabled until their end-to-end receipts are tested.

## Intended flow

```text
new or changed file
  -> local deterministic classifier
  -> >= 0.90: carry cleanly
  -> otherwise: bounded DeepSeek classification
       -> >= 0.90: carry cleanly
       -> >= 0.60: carry provisionally + notify
       -> below 0.60 / needs human: hold + notify
```

“Carry” means update intelligence records and generated views. Move, rename,
delete, publish, promote and canonize remain separately reviewed actions.
