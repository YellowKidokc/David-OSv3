# NABLA-χ UNIVERSAL SEMANTIC CLASSIFICATION STANDARD v1.0

> Preserved reference (author: David Lowe). This is **audit mode** — the full
> defensibility system. Everyday filing uses the 3-level model in
> `CHI_FILING_LEVELS.md`; only serious claims (papers, formal proofs, public
> claims, dangerous overclaims) run this full standard.

Purpose: classify, name, decode, compress, grade, and coherence-test any
document, claim, file, dataset, paper, note, transcript, or artifact.
Core principle: **classify what the artifact IS and DOES, not what it talks about.**

Separate, never collapse: (1) artifact identity, (2) semantic orientation,
(3) coherence scoring, (4) claim type, (5) evidence/attestation,
(6) constructive/destructive regime, (7) risk, (8) repair path.

## Part 0 — Hard boundaries
1. Does not magically know facts. 2. Does not replace evidence. 3. Does not
prove theological/metaphysical/empirical/historical claims by classification
alone. 4. Classifies structure, coherence, claim-mode, risk, evidence fitness.
5. Truth requires claim-type + attestation + evidence bridge + coherence.
6. Address identifies the artifact. 7. χ profile evaluates coherence. 8. Grade
audits defensibility. 9. Evidence bridge connects support to claim. 10. Regime
map detects constructive vs destructive expression.

## Section 1 — Artifact naming: `D/N/V/A/U/R :: VECTOR :: HASH`
- **D Domain**: THEOPHYSICS, SCIENCE, LAW, MEDICINE, FINANCE, PERSONAL, TECH,
  EDUCATION, GOVERNANCE, ART, BUSINESS, RELIGION, HISTORY, MDA, DATA, UNKNOWN.
- **N Named Entity**: the specific paper/system/claim/dataset (X if unknown).
- **V State**: D draft, W working, F final, P published, A archived, X deprecated, U unknown.
- **A Audience**: SELF, INTERNAL, TEAM, AI_RESEARCH, PUBLIC, PUBLIC_RESEARCH,
  ACADEMIC, CLIENT, RESTRICTED, LEGAL, UNKNOWN.
- **U Use** (one only): I inform, B bind, T transform, R record.
- **R Risk**: R0 public/low, R1 internal research, R2 private/PII, R3
  legal/financial/formal-consequence, R4 life/safety-critical.
  (Filing R = Risk; semantic R = Relation/Bond — never confuse.)

## Section 2 — Ten-variable orientation vector (address: 0 or 3 only)
G Authority/Ground · M Mechanism/Action · E Entropy/Disorder · S Identity/Self ·
T Time/Sequence · K Knowledge/Info · R Relation/Bond · Q Experience/Felt ·
F Faith/Trust · C Coherence/Unity.

## Section 3 — Six no-drift rules
1. Artifact, not topic. 2. Binary orientation (0/3 only) for the address.
3. Confidence is separate. 4. E = artifact disorder only (corrupt/redacted/
fragmented), not dark subject matter. 5. C = explicit integration *function*,
not "well written." 6. Address is not truth.

## Section 4 — Hash construction
Tie-break order: E → C → G → K → M → T → R → F → S → Q. Rank all vars high→low
(3s before 0s; ties by tie-break order). Pair strongest with weakest inward:
`[#1·#10][#2·#9][#3·#8][#4·#7][#5·#6]`. Pair 1 is an anchor, not the whole meaning.

## Section 5 — Confidence & agreement
Per-variable confidence 0.00–1.00; flag < .75. Cross-model agreement via Hamming
distance over the 10 binary vars (0 exact, 1 strong, 2 adjudicate, 3+ unstable).

## Section 6 — Continuous χ coherence
`χ = G · M_eff · E_signal · S_eff · T · K · R · Q · F · C`, each channel 0–1.
`M_eff = (1 + M_raw)/2`; `S_eff = exp(-η·S_prod)`; `E_signal` = signal fidelity
(NOT artifact-disorder E). Never use raw S_prod as a positive multiplier or raw
signed M inside χ.

## Section 7 — Constructive/destructive regime map
Every active law/channel labeled constructive | destructive | mixed | unknown.
A high score can be coherent truth or coherent deception depending on regime.
Laws 1–10 each carry a constructive and destructive reading (Gravity/Grace↔Sin;
EM/Truth↔Deception; Strong/Covenant-love↔Captivity; Thermo/Judgment-paid↔Heat-death;
Information/Logos↔Noise-lie; Quantum/Faith↔Fear-collapse; Relativity/Alignment↔
Frame-lock; Weak/Atonement↔Sin-decay; Coherence/Christ↔Decoherence). Law 9 is
one-directional down; Law 10 is one-directional up (integrator).

## Section 8 — Claim type before truth
TRUTH_MODE ∈ {AXIOM, PRE_ASSUMPTION, EMPIRICAL_EVENT, INSTRUMENT_MEASUREMENT,
HISTORICAL_RECORD, INSTITUTIONAL_FACT, LEGAL_FACT, MATHEMATICAL_PROOF,
FORMAL_DERIVATION, CLASSIFICATION, INTERPRETATION, SYMBOLIC_TRUTH, MORAL_CLAIM,
THEOLOGICAL_CLAIM, EXPERIENTIAL_REPORT, PREDICTION, FICTIONAL_CLAIM,
CULTURAL_TRUTH, UNKNOWN}. ASSUMPTION_LOAD A0–A5. ATTESTATION_MODE ∈
{direct_observation, instrument_measurement, public_record, legal_record,
institutional_recognition, mathematical_proof, formal_machine_check,
scriptural_authority, expert_consensus, self_report, statistical_inference,
model_prediction, historical_testimony, cultural_practice, unknown}.
Rule: χ organizes evidence; it does not create it.

## Section 9 — Defensibility snapshot
CLAIM_ARCH → EVIDENCE_CHAIN → KILL_ARCH → EQ_SEM → DOMAIN_BOUNDARY →
REVIEWER_SEEDS → LEDGER_SCHEMA → OVERSTATE_PATTERN → BENCHMARK_ANCHOR →
CROSS_DEP → EIGHT_GAPS. Equation statuses: DERIVED, PROVED, PROPOSED,
INTERPRETIVE, PRESENTATIONAL, SYMBOLIC_FORMALISM, OPERATIONAL_MODEL, ANALOGY,
RHETORICAL_MATH. High-risk words: proves, mathematically proven, undeniable,
impossible, refuted, destroyed, only, definitive, settled.

## Section 10 — Four separate grades (never collapsed)
Academic_Readiness · Framework_Coherence · Public_Communication · Risk. Each:
score, grade, reason, top_positive, top_deduction, fix_to_improve.

## Section 11 — Pressure states
static · compression · strongest-objection · time · translation · evidence ·
implementation · **Fruit** · falsification · hostile-misuse. Fruit pressure: does
living the claim tend toward Love/Joy/Peace/Patience/Kindness/Goodness/
Faithfulness/Gentleness/Self-Control — or their opposites?

## Section 12 — Output JSON schema
Returns a single JSON object with: `artifact`, `address`, `filing_decode`,
`semantic_vector` (G..C = 0/3), `confidence_by_variable`, `hash_verification`,
`minimal_decode`, `claim_analysis[]`, `chi_evaluation`, `defensibility`,
`review`, `reconstruction`. (Full schema retained in project history / prompts.)

## Sections 13–15 — 30 design rules · decode procedure · calibration examples
30 rules restate the boundaries (artifact not topic; binary address; confidence
separate; E = disorder; C = integration; claim-type before truth; χ organizes,
never creates evidence; strong claims need kill conditions; every score needs a
ledger; flag review rather than invent certainty). Calibration examples: pilot
pre-flight checklist (G/M/T/K/R dominant, no C), Theophysics Logos Principle
(G/M/T/K/R/Q/F/C), redacted FBI doc (E=3 for obstructed access, not dark topic),
Santa Claus (split into historical/cultural/empirical/symbolic claims).

## Final output rule
Return structured JSON. Never collapse classification, coherence, truth,
evidence, and risk into one undifferentiated verdict.
