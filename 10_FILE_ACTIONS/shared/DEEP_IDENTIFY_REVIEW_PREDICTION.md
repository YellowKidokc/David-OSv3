# Deep Identify crew review: Prediction GUI and calibration

Date: 2026-11-12. Independent Codex review. Read-only source inspection; no live corpus benchmark or GUI acceptance test.

## 1. Architecture — BREAK

Family discovery is title-root gated. References are collected into `ref_groups` but never used to create groups; vocabulary only boosts existing title groups. Differently named relatives cannot be discovered by those signals (`deep_identify.py:392-433,467-475`). Keep the five stages but generate candidates from each connector independently.

## 2. Lexicon — IMPROVE

Prefer versioned JSON exported from the canonical workbook, validated before publication, with workbook hash, exporter/schema version and per-rule provenance. Keep document type, law affiliation and claim-strength/danger assessments as separate outputs. Claim strength is not confidence that a document classification is correct. Workbook contents were not inspected in this scoped pass.

## 3. Prediction GUI — IMPROVE

The actual GUI harness is vendored locally under `03_CLASSIFY/02_CLASSIFICATION`, rather than the hub HTTP predictor. Adapt to its Prediction/Candidate contract, register an engine and submit through the runner. Notification and outcome scoring are separate operations.

Actual contract:

- `harness/contract.py:38-54`: Candidate(value, confidence, reason); Prediction(engine,target,context_key,candidates,markers,guidance,timestamp,id).
- `harness/contract.py:66-89`: engine implements fit(events) and predict(context); an empty candidate list abstains.
- `harness/runner.py:58-76`: Runner.shadow(context) runs registered engines and records predictions.
- `harness/runner.py:80-95`: resolution is by context key and target. Use a distinct target such as family_assignment, and include stable file identity plus assessment version in context so unrelated files do not share outcomes.
- Store connector evidence, source hashes, lexicon/version identifiers, scan coverage and score_kind="heuristic" in markers. Candidate value should be a stable family signature rather than FAM-001.
- `03_CLASSIFY/00_SHARED/notify.py:26`: toast(title, body, open_path) supplies optional review notifications, not ledger persistence.
- `hub/api/routes_prediction.py:12-35,54-65` is a separate move/rename API with destination/name corrections. It does not supply the requested family-review contract.

Initial policy: persist discoveries, show one grouped review summary per scan, and suppress duplicate toasts using a stable assessment signature. No numerical confidence threshold is justified yet. Collect labeled family assignments, measure precision/recall and calibration by score band, then select thresholds. Feed user outcomes to the harness; never treat classifier output as confirmed training feedback.

## 4. Scoring — BREAK

Values are heuristic scores, not measured probabilities. Document types can receive substantial scores with zero marker hits. Domain scores depend on vocabulary size. Overall identity averages unrelated signals and penalizes missing frontmatter/sections (`deep_identify.py:274-296,320-344,616-624`). Family title and numbering signals are correlated. Fixed orphan probability 0.8 is uncalibrated (`:450-479,508-513`).

Separate evidence scores from calibrated probabilities. Keep component scores and abstention/extraction status; calibrate with held-out labels and report coverage alongside precision and recall.

## 5. What breaks first — BREAK

Inconsistent names fail the central discovery claim. Traversal-dependent first-five vocabulary scoring, sequential FAM identifiers and scan caps destabilize repeated-run results (`deep_identify.py:429-433,468-470,483,551-559`). Use deterministic traversal and stable family identities; report incomplete scan coverage explicitly.

## Overall confidence

The requested probability of correctly identifying relationships in `C:\theophysics\faiththruphysics.com` is not estimable from this inspection. Confidence in these source findings is high; corpus performance remains unmeasured. Benchmark a labeled sample including differently named relatives, same-title unrelated files, duplicate positions and partial scans before assigning a percentage. A forced percentage would contradict the requested scoring honesty.
