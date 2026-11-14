# Rule Brick

Rule Brick is the shared, advisory contract for filesystem work in David-OS.
It centralizes human-readable principles, machine-readable questions, evidence-backed
predictions, and before/during/after work receipts.

It does **not** rename, move, delete, canonize, or approve anything.

## Lifecycle

```powershell
python -m rule_brick.cli before --agent codex --intent "audit names" --root D:\Example
python -m rule_brick.cli questions
python -m rule_brick.cli after --session SESSION_ID --status complete --outcome "report written"
```

Python workers use `RuleBrick.before_work()`, `record_prediction()`, and
`after_work()`. State defaults to `.data/rule-brick/rule_brick.sqlite` and should
remain runtime-only.

## Statistical meaning

`score_signals()` produces an evidence-weighted ranking score and a separate
coverage value. It deliberately does not multiply evidence as though folder names,
file names, media, and sibling structure were independent. Scores become calibrated
probabilities only after predictions are resolved against actual outcomes.
