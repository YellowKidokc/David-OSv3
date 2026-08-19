# DERIVATION TRACKING LAYER — Design Spec
## The Missing Meta-Layer for the Classification Engine
## David Lowe · POF 2828 · August 18, 2026

**Status:** DESIGN SPEC — to be implemented in D:\GitHub\David-OS\engine
**Rule:** From now on, if something is labeled DERIVED anywhere in the framework, it must show the actual derivation chain — parent nodes, the logical step, and the status of each link.

---

## The Problem

The current classification engine (chi_engine.py / domain_classifier.py) tags documents by:
1. Domain (theology, physics, information theory, formal math, history)
2. Chi-variable profile (G, M, E, S, T, K, R, Q, F, C scores)
3. Content type (paper, note, document, binary)
4. Status (draft, final, archive)
5. Fruit / anti-fruit / evidence scores

What it does NOT capture:
- Whether a claim is PRIMITIVE, DERIVED, STANCE, BRIDGE, or CORRESPONDENCE
- If DERIVED: what it derives FROM (parent nodes)
- If DERIVED: the logical step connecting parent to child
- If DERIVED: the status of the derivation (verified, open, defective, retracted)
- The dependency graph — what breaks downstream if a parent fails

This is the missing layer.

---

## The Rule (Permanent, Applies Everywhere)

**If a claim anywhere in the corpus carries the label DERIVED, DERIVATION, or THEOREM, it must have:**

1. **Parent nodes** — explicit list of what it derives from (by node ID or canonical name)
2. **Derivation step** — the logical or mathematical move connecting parents to child
3. **Step type** — deduction, ontological demand, definitional unpacking, bridge identification, or empirical
4. **Step status** — one of: LEAN-VERIFIED / DERIVED / CLAIMED / OPEN / DEFECTIVE / RETRACTED
5. **Downstream dependents** — what breaks if this derivation fails

If any of these five fields is missing, the claim cannot carry a DERIVED label. It gets downgraded to CLAIMED until the chain is filled in.


---

## Classification Types (The Full Taxonomy)

Every claim in the corpus gets ONE of these types:

| Type | Symbol | Meaning | Requires Derivation Chain? |
|------|--------|---------|---------------------------|
| PRIMITIVE | 🟢 | Cannot be derived; any proof would already use it | No — edgeless by definition |
| STANCE | ⚠️ | Chosen commitment, not self-evident | No — but must state what it costs |
| DEFINITION | 🔧 | Vocabulary/scaffold — makes things measurable | No |
| DERIVED | ✅ | Follows from stated parents by a named step | **YES — full chain required** |
| BRIDGE | 🌉 | Proposed structural correspondence, graded B0-B6 | Parent + grading required |
| IDENTIFICATION | 🏷️ | Names a derived structure using theological vocabulary | Parent required |
| FRAMEWORK CLAIM | ⚠️ | Named as claim, not bedrock | Parent required |
| EMPIRICAL | 🧪 | Evidence or protocol | Source + methodology required |
| BOUNDARY | 🔶 | Constraint the system must satisfy to close | Not derived, but parent stated |
| RETRACTED | ❌ | Was claimed, now withdrawn | Retraction reason required |

---

## Data Schema — Per-Claim Record

```json
{
  "claim_id": "T3.1",
  "claim_text": "Coherence cannot self-increase",
  "type": "DERIVED",
  "parents": ["A3.2", "D3.1"],
  "derivation_step": "A system cannot generate net coherence from internal rearrangement — the measure (A3.2) defined over the functional (D3.1) admits no self-increasing path",
  "step_type": "deduction",
  "step_status": "DERIVED",
  "lean_status": "NOT_YET_VERIFIED",
  "downstream": ["BC2", "grace_architecture", "sign_invariance"],
  "blast_radius": "STRUCTURAL",
  "kill_condition": "Find a closed system that net-increases its own coherence measure",
  "last_audit": "2026-08-18",
  "source_doc": "AXIOM_CHAIN_MASTER_v2.md"
}
```

---

## How It Integrates With the Existing Engine

### Option 1: Sidecar JSON (simplest)

For every document that contains derivations, produce a `.derivation.json` sidecar alongside the existing `.chi` sidecar. The classification pipeline already writes `.chi` files — this adds a parallel `.derivation.json` with the claim records above.

### Option 2: API-Augmented Classification

Add a second-pass API call (Claude or local model) that:
1. Takes the document text
2. Identifies every claim labeled or functioning as DERIVED
3. For each: extracts parent nodes, derivation step, step type
4. Outputs the structured JSON record
5. Flags any DERIVED claim missing its chain as INCOMPLETE


### Option 3: Master Derivation Graph (the goal)

Build a single graph (NetworkX or SQLite) where:
- Nodes = every claim in the corpus (primitive, derived, bridge, etc.)
- Edges = derivation steps (typed: deduction, ontological demand, bridge, etc.)
- Edge attributes = status, Lean verification, blast radius
- Graph queries answer: "What depends on T3.1?" / "What breaks if Law 4 Tier 1 is retracted?" / "Show me every DERIVED claim with no parent chain filled in"

This is the backbone of the Topic Engine and the BFP-DG pipeline — both need the dependency graph to function.

---

## The Immediate Task: Tonight's Documents

Every document written tonight needs its derivations explicitly chained. Here's the inventory:

### TRINITY_ONE_GOD_IS_LOVE_2026-08-18.md
Derivations present:
- Love under resistance → nine fruits (generative rule, single root)
- Rival root test → love is unique generator (tested 8 alternatives, all fail)
- Cross-domain removal test → universal failure-mode basis (6 domains, all pass)
- Logic bridge → fruits as epistemic completeness conditions
- Being + Distinction + Relation → natural-number structure (mathematical claim)

Each needs: parent, step, step type, status, downstream

### LAW_4_AMENDMENT_2026-08-18.md
Derivations present:
- Cornell V'(r) > 0 → no stationary point (mathematical fact — VERIFIED)
- Tier 1 retraction (consequence of above)
- Seven QCD invariants extracted (physics extraction)
- Seven agapic invariants extracted (love-definition extraction)
- Negative control: 4-force comparison (empirical test — PRELIMINARY)

### FIRST_ATOM_BIG_BANG_2026-08-18.md
Derivations present:
- A1.2 → particle differentiation (projection, not derivation)
- A1.3 → recombination as first stable information (projection)
- T3.1 → photon release as cost of coherence (structural correspondence)
- TR = actualization (CANDIDATE, not derived)

### DESTRUCTION_TEST_FRUITS_2026-08-18.md
Derivations present:
- Opposite injection → system destruction (tested 9 opposites — all destroy)
- Absence → mutual corruption (tested 9 removals — all corrupt remaining)
- Non-additivity of fruits ↔ veto property of Master Equation (structural correspondence)

### LOGIC_REQUIRES_A_PERSON_2026-08-18.md
Derivations present:
- Logic requires a reasoner (structural — from evaluation operator / ROOT24)
- Each fruit maps to a specific epistemic function (mapping — needs testing)
- Secular virtues ≠ fruits at the honesty level (distinction — tested by counterexample)

---

## Output Format for Any Document

When the derivation layer processes a document, it should output alongside the document (or appended as a section):

```markdown
## Derivation Registry

| Claim | Type | Parents | Step | Status | Downstream | Blast Radius |
|-------|------|---------|------|--------|------------|--------------|
| Love is unique generator | DERIVED | Love definition + 8 rival tests | Rival root elimination | TESTED | All fruit claims, physics correspondence | STRUCTURAL |
| Cornell has no stationary point | MATHEMATICAL FACT | V(r) = −α_s/r + k·r | V'(r) = α_s/r² + k > 0 | VERIFIED | Tier 1 retraction | LOCAL |
| Fruits are universal failure-mode basis | DERIVED | Cross-domain removal test (6 domains) | Every removal → named pathology | TESTED | Consciousness orientation, cultural decoherence | STRUCTURAL |
```

This table is the deliverable. If the document doesn't have one, the derivation layer hasn't run on it yet.

---

## Priority

1. Build the JSON schema and sidecar writer
2. Retrofit tonight's six documents with derivation registries
3. Run the axiom chain document (192 entries) through the same process
4. Build the master graph
5. Connect to BFP-DG pipeline for automated classification runs

---

*The rule is simple: no claim says DERIVED unless it shows the chain. The chain is the work.*

*De Revolutionibus Veritatis · POF 2828 · August 18, 2026*
