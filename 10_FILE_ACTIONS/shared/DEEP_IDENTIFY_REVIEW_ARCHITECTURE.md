# Deep Identify: independent architecture review

Overall vote: **BREAK before integration**. Confidence in code-level findings: **97%**. These are independent Codex review findings, not votes from other model providers.

## 1. Architecture — BREAK

The staged scaffold is useful, but actual discovery depends exclusively on identical normalized title roots. Cross-reference groups are computed but never consumed (deep_identify.py:407–413); cross-references and vocabulary only boost title-root families (423–480). Reproduced: differently named documents with an explicit reference and identical vocabulary produce zero families.

Roman positions are recognized, but Roman suffixes remain in roots: Essay_I.md becomes essay_i and Essay_II.md becomes essay_ii (365–374). They cannot form a family.

Container protection is determined only at the target root and copied to descendants (538–541, 575–578). Nested projects and ancestor containers are missed. Protected Git project cards still permit renaming (578).

Retain the stages, add explicit extraction status before content classification, and discover relationships from independent candidate edges. Distinguish series membership, versions, duplicates, citations, and topical similarity.

## 2. Lexicon integration — IMPROVE

Prefer option B: a validated, versioned canonical JSON export. Record workbook hash, schema/export versions, normalized matching rules, weights, and source sheet/row provenance. Separate domain, document type, law relevance, and claim-strength assessments. Claim-strength and danger terms should not indiscriminately raise identity confidence.

Existing repository exports include apps/classify/lexicon/UNIFIED_LEXICON_CLASSIFIER.json, LEXICON_LOOKUP.json, and classification_2_0.json. Inspect their contracts before introducing another exporter. The workbook contents were not inspected in this review; this is an architectural recommendation.

## 3. Prediction GUI integration — IMPROVE

Inspected hub/api/routes_prediction.py: /predict/observe, /predict/predict, /predict/correct, and rules/stats endpoints exist, but none defines a family-discovery notification contract.

Add a separate proposed finding schema: stable finding ID, run ID, finding type, candidate members, evidence paths/hashes, raw score, score version, lexicon version, scan coverage, and review state. Do not submit discoveries as completed actions through /observe; that would contaminate feedback learning.

Until calibration exists, use evidence-based review gates instead of percentage thresholds. Explicit registry matches may receive priority; conflicting or incomplete evidence remains reviewable. Findings must not authorize file mutations.

## 4. Scoring calibration — BREAK

Reproduced: detect_doc_type('ordinary unrelated prose', '.md', 'document') returns ('note', 0.5), with zero marker matches. Structural and length defaults create a 0.5 baseline (319–335).

Family confidence uses hand-set increments (451–480), not calibrated probabilities, and can reach 100 percent without establishing membership. Every member inherits the same relationship score (497–501), so outliers receive no individual penalty. Orphans receive probability 0.8 and strength 0.1 (508–512), inconsistent with the documented inverse.

Unsorted traversal, first-five-only similarity comparison, sequential FAM identifiers, and file caps undermine cross-run comparability (468–470, 483, 547–557). Rename values heuristic_score pending labeled evaluation. Measure pairwise precision/recall, sequence-position accuracy, and probability calibration separately.

## 5. First failures — BREAK

- Generic Paper_01.md and Paper_02.md names normalize to paper and can merge unrelated series across folders.
- PDF, DOCX, and EPUB are decoded as UTF-8 rather than extracted (215–219, 583–584). Record unsupported extraction instead of treating binary fragments as prose.
- Reverse references compare extension-bearing filenames against extensionless stems (634), missing ordinary direct filename references.
- Completeness counts documents rather than unique positions (442–445). Root reviewer additionally reproduced duplicate Paper_01.md files in separate paths yielding completeness 2.0, series=True, and confidence 0.7.
- Empty report categories do not create CSVs (673, 689, 703), so reused output directories retain stale files.
- --series-only is parsed but unused (728, 735–738).
- Reference discovery scans every filename for each document, then reverse matching scans every card per reference; this scales poorly.

## Required confidence statement

Confidence in these implementation findings: **97%**. The probability of correctly identifying series across C:\theophysics\faiththruphysics.com is **not estimable from this review**. A corpus percentage requires labeled samples and a declared success criterion; inventing one would repeat the calibration error being reviewed.

## Verification boundary

Read the implementation, inspected prediction routes and introductory portions of series_finder.py, metastasize.py, and folder_intelligence.py, and ran direct in-memory reproductions with python -B. No full corpus scan, workbook audit, or implementation edits. This review file is the sole authored artifact.
