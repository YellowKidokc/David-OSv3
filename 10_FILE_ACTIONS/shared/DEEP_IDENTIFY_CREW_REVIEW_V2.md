# Deep Identify — crew ballot, revision 2

Draft for David's vote. Original brief by Fable and David, November 12, 2026.

Review the current prototype and vote on the smallest useful next step. The scanner reads source files and writes a report. Treat file classifications, family suggestions, and protection flags as advisory. Use synthetic fixtures and a separate output directory for experiments.

## Review inputs

- [Classifier](deep_identify.py), [original brief](DEEP_IDENTIFY_CREW_REVIEW.md), and [rule-brick questions](../../rule_brick/questions.json).
- [Series finder](series_finder.py), [connection walker](metastasize.py), and [folder profiler](folder_intelligence.py).
- Canonical workbook named lexicons_master_enhanced_v2_classification_2026-11-06.xlsx. Verify the source path, revision, and sheet headers. Compare the existing exports in [apps/classify/lexicon](../../apps/classify/lexicon) before proposing a new exporter.
- Inspect the Prediction_GUI checkout at D:/GitHub/Prediction_GUI and start with notifications/engine.py, notifications/adapters/series_registry.py, and API/schemas/notification-request.v1.json. Check whether the selected entry point can enqueue quietly and deduplicate retries.

## Five votes

1. **Architecture.** Keep container and file kind as context, evaluate domain and document type from their own evidence, and run relationship discovery across the scanned set. Should shared roots, resolved links, or distinctive vocabulary each nominate candidates? What additional evidence should a candidate need before it becomes a family suggestion? Test different names with explicit links and similar names with unrelated content. Address nested protected folders and ambiguous basename matches.
2. **Lexicon.** Vote A (load XLSX at scan time), B (generate versioned JSON), or C (reuse the existing SQLite source if its ownership and schema are verified). For B, propose an explicit exporter with validated sheet headers, source SHA-256, schema version, deterministic output, and a visible missing/invalid status at runtime. Specify the mapping from DOC_TYPE_PATTERNS to emitted labels, including unmapped labels. Treat LAW_KEYWORDS as topical evidence and SEMANTIC_BUCKETS as claim-language annotations. Show how phrase boundaries, overlap, and conflicting markers affect the result. Explain how to detect stale exports when publishing a new revision.
3. **Prediction_GUI.** Identify the actual ingestion point and record format. Would a completed report imported into a review queue be sufficient for the pilot? Propose the smallest adapter that preserves evidence, scan coverage, and stable identifiers across retries. Explain how you would suppress duplicates and handle a partial scan. Recommend when to surface a family, candidate orphan match, or internal numbering gap. Justify any notification threshold with evidence.
4. **Scoring.** Treat current values as heuristic scores. Propose per-label evidence, runner-up margins, abstention, and separate family scores. Specify what you would measure on human-labeled folders, including per-label precision/recall, family pair precision/recall, and coverage after abstention. Say how to keep near-duplicate versions out of both sides of a tuning/evaluation split. Test a text with zero markers and a series with repeated position numbers.
5. **First failure.** Trace one ordinary CLI run from scan through JSON/CSV publication. Reuse the output directory for a second scan with empty result sets. Name the first failure you can show, cite the code, and give one acceptance test. Also flag any traversal or matching cost that remains unbounded under --max-files.

## Ballot format

For each numbered question, give HOLD (keep), BREAK (blocks pilot), or IMPROVE (change recommended), plus your confidence in that judgment as a percentage. Cite a path and line or describe a small test with its observed output. State any missing input and one result that would change your vote. Include the A/B/C selection for question 2.

Finish with an overall pilot vote, the one change you would land first, and the smallest test batch you would use to decide whether to expand. Give a corpus accuracy estimate only if you have labeled results and can state the denominator and scan coverage. David makes the integration decision.
