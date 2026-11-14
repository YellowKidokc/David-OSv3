# Deep Identify Crew Review — Lexicon and Integration

Date: 2026-11-12
Reviewer: independent Codex crew agent
Scope: read-only code and reference inspection. No implementation changes or live corpus scan.

Overall vote: **BREAK integration; retain and repair the design.**

## 1. Architecture — IMPROVE

The five-level order is useful, but content acquisition needs an explicit stage and status. `_read_sample` reads UTF-8 text for PDF/DOCX as well as Markdown (`deep_identify.py:215–221,583–584`). These formats require extractors or an explicit unsupported state. Level 0 checks the selected root and stamps its flags onto descendants (`538–578`); nested project protection is missing.

## 2. Lexicon — IMPROVE; choose B

Existing infrastructure already uses JSON: `apps/classify/src/run.py:28` loads `apps/classify/lexicon/LEXICON_LOOKUP.json`; `UNIFIED_LEXICON_CLASSIFIER.json` retains source collection names. These flattened outputs are not automatically complete substitutes for the workbook: the lookup chiefly maps terms to axes, while semantic rows contain polarity, weight, danger, contexts and recommended actions.

Export a versioned artifact with workbook SHA-256, exporter/schema versions, sheet and row provenance, normalized phrases, and preserved metadata. Validate weights and conflicting entries. Keep document type, law/topic relevance and claim-risk assessments as separate axes; danger is not evidence of document identity or relationship strength. Define explicit refresh/rebuild behavior when the workbook changes.

Located six workbook variants in `.data/classification`, including `LEXICON_MASTER_v2_UNIFIED.xlsx`, its JEV-scored version and enhanced variants. The specifically named November 6 workbook was not located there, and workbook contents were not opened. `03_CLASSIFY/00_SHARED/CLASSIFICATION_SOURCES.json:552–606` inventories LAW_KEYWORDS, DOC_TYPE_PATTERNS and SEMANTIC_BUCKETS headers. `engine/chi_engine.py:247–310` already implements a workbook loader preserving several semantic fields, but merges seed terms and drops some context fields; reuse carefully. No authoritative Jev/TypeSafe SQLite vocabulary contract was established in this inspection.

## 3. Prediction GUI — IMPROVE

Use the existing contract rather than inventing notification JSON: `03_CLASSIFY/02_CLASSIFICATION/harness/contract.py` defines Event, Candidate and Prediction. Emit an observation Event for completed scans; use a separate relationship-proposal Prediction with evidence, file identities, run ID, vocabulary version and score semantics in markers. Start with review-only proposals. Numerical notification thresholds cannot be justified by current uncalibrated scores; deduplicate changes and prioritize conflicting evidence/gaps. Delivery and GUI refresh behavior still need verification against the actual runner and ledger.

## 4. Calibration — BREAK

Current confidence values are heuristic scores, not probabilities. Nonempty plain prose can receive note confidence 0.5 without a marker because length and section defaults supply that baseline (`318–343`). Family confidence starts at 0.6 and adds correlated signals (`450–480`). Members inherit the same relationship strength, while orphans receive an unsupported 0.8 probability (`497–512`). Preserve raw features/scores; calibrate against labeled family pairs and held-out series, reporting precision/recall and extraction coverage. Until then, label confidence as heuristic support.

## 5. What breaks first — BREAK

`orphans.csv` fails for any orphan: its DictWriter omits `extrasaction="ignore"` (`706`), then receives the entire FileCard dictionary (`709`), which contains extra fields. This finding follows directly from code inspection; no execution reproduction was performed by this reviewer.

The promised three independent discovery signals are not implemented: `ref_groups` is constructed but unused (`407–413`); families originate exclusively from equal title roots (`423–428`). Cross-references and vocabulary only boost existing groups, so inconsistent title roots cannot be rescued by those signals.

## Requested overall confidence

The chance of correctly identifying series relationships in `C:\theophysics\faiththruphysics.com` is not empirically estimable without a labeled sample and an operational definition of correct identification. An asserted percentage would repeat the calibration defect. Confidence in the code-level findings above: **95%**; this is reviewer confidence, not measured family accuracy.
