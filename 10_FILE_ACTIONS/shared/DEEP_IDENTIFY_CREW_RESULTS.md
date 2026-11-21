# Deep Identify crew round ? 2026-11-12

Three independent Codex reviewers; no external Opus or Kimi calls. Production code unchanged.

| Question | Architecture reviewer | Lexicon reviewer | Prediction reviewer |
|---|---|---|---|
| Architecture | BREAK | IMPROVE | BREAK |
| Lexicon | IMPROVE: B | IMPROVE: B | IMPROVE: B |
| Prediction GUI | IMPROVE | IMPROVE | IMPROVE |
| Calibration | BREAK | BREAK | BREAK |
| First failures | BREAK | BREAK | BREAK |

Overall: repair before integration. Keep the five-stage scaffold.

## Priority findings

1. Orphan CSV export raises ValueError: DictWriter receives full card fields without extrasaction=ignore (deep_identify.py:706?709).
2. Cross-reference groups are unused. Vocabulary and references only boost identical-title groups; inconsistent-name families cannot be discovered (407?428).
3. Protection is stamped from the scan root. Nested/ancestor projects are missed, and protected Git cards remain renameable (538?578).
4. Duplicate positions inflate completeness. Root reproduced two Paper_01.md cards giving completeness 2.0, series=True, score 0.7.
5. Root reproduced unrelated prose classified note at 0.5 without marker evidence. Scores are heuristics, not measured probabilities.
6. PDF/DOCX/EPUB need extraction status and format-aware readers. Current code decodes them as UTF-8.
7. Stable ordering, family signatures, scan coverage and versioned evidence are needed for repeatable assessments. Sequential FAM IDs are not canonical identities.

## Lexicon decision

Choose B: validated, versioned canonical JSON with workbook SHA-256, schema/exporter versions and sheet/row provenance. Inspect existing apps/classify/lexicon exports and engine/chi_engine.py before adding infrastructure. Preserve polarity, weights, danger and context. Keep document type, domain/law relevance and claim risk separate.

The exact November 6 workbook was not located in the inspected classification directory; workbook contents were not verified. Do not silently substitute another variant.

## Prediction integration

Use 03_CLASSIFY/02_CLASSIFICATION/harness/contract.py Candidate/Prediction and register an engine through Runner.shadow. Use a distinct family_assignment target and stable per-file assessment context. Preserve evidence and score semantics in markers. Optional review toasts use 03_CLASSIFY/00_SHARED/notify.py; the hub move/rename predictor is a separate contract.

Persist proposals separately from confirmed user outcomes. A completed scan observation must never imply an accepted family assignment. Initially show a grouped, deduplicated review summary; select numeric thresholds only after labeled evaluation.

## Confidence and verification

All reviewers declined to invent a percentage for accuracy on the requested live corpus. No labeled corpus benchmark or full corpus scan was performed. Architecture reviewer confidence in code findings: 97%; lexicon reviewer: 95%; prediction reviewer gave qualitative high confidence. These are reviewer judgments, not measured classifier accuracy.

Root ran isolated temporary/in-memory reproductions for zero-marker classification, duplicate-position completeness and Git rename flags. Separate reviewer reports provide detailed evidence. No production code fixes were authorized by this review round.
