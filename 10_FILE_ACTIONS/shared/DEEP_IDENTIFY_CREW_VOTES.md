# Deep Identify — crew round and decision

November 12, 2026. Two independent Codex reviews of the original brief and working prototype, followed by the revised ballot. Confidence is the reviewer's confidence in the vote. Corpus accuracy remains unmeasured.

| Question | Reviewer 1 | Reviewer 2 | Evidence |
| --- | --- | --- | --- |
| Architecture | BREAK 99% | BREAK 99% | Two differently named documents with reciprocal links yielded two orphans. Links and vocabulary only boost title-root groups. |
| Lexicon | IMPROVE 96%, B | IMPROVE 95%, B | Existing classifier JSON exports give B a starting point. Verify the exact workbook revision and map workbook labels to scanner labels explicitly. |
| Prediction_GUI | IMPROVE 96% | IMPROVE 99% | The notification inbox has a reusable item contract. The HTTP path uses desktop and auto-advice defaults, and the store inserts rows without retry deduplication. |
| Scoring | BREAK 99% | BREAK 99% | A marker-free sample returned note at 0.50. Repeated position 1 produced completeness 2.0. |
| First failure | BREAK 99% | BREAK 98% | An empty rerun left prior file-card and orphan CSVs beside a current JSON report with zero files. Basename resolution also admits self-links and ambiguous matches. |
| Overall integration | BREAK 99% | BREAK 98% | Both reviewers would fix and test the report and family behavior before integration. |

## Proposed decision for David

**Approve a report-only pilot after the following checks pass.** My vote is HOLD on the five-stage structure, IMPROVE with option B for lexicon delivery, and BREAK on integrating the current reports into Prediction_GUI.

1. **First patch: publish a complete report for every successful run.** Empty CSVs get headers. Readers see a single completed run, including scan coverage and skipped/error counts. Reuse an output directory in a test and verify that no prior rows survive an empty rerun.
2. **Fix family evidence.** Resolve links to paths, exclude self-links, and surface ambiguous targets. Let resolved links nominate candidates alongside title roots. Count unique positions, flag competing versions at the same position, and report gaps as missing positions within the observed range. Test unrelated same-name files, differently titled reciprocal links, and repeated positions.
3. **Try B against a labeled batch.** Check the existing exports against the approved workbook and record the source digest and mapping. Start with document-type markers. Report law vocabulary as topical evidence and semantic bucket hits as claim-language annotations. Compare baseline and overlay on the same labeled folders, with related versions held together. Report precision, recall, and abstention coverage.
4. **Revisit notifications after the pilot.** Start with one opt-in inbox batch from a completed report. Verify retry deduplication and quiet review-only behavior before wiring the adapter. Use measured performance to set notification rules.

Vote on this sequence, or name the first step you would change. See [revised crew ballot](DEEP_IDENTIFY_CREW_REVIEW_V2.md).
