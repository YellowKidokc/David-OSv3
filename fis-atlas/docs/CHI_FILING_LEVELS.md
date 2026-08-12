# χ Filing — the buildable version (three levels, not one monster)

The correction to the full standard: **don't run the 74-factor audit on every
file.** Three levels.

## Level 1 — Practical filing
`PRIMARY_FACTOR + ENTITY + STATE + DATE + SHORTCODE`
```
K__LOGOS_INFORMATION__W__20260618__LAW06.md
G__GRACE_EXTERNALITY__F__20260618__LAW01.md
C__MASTER_EQUATION_KERNEL__F__20260618__CHI.md
```
Answers: *which part of χ does this file mainly serve?*

## Level 2 — Ten-factor rating (THE classifier to build first)
Every file rated on the ten Master-Equation variables, **0–3**:
```
0 = absent · 1 = weak trace · 2 = active/supporting · 3 = dominant/primary
G Ground  M Mechanism  E Entropy  S Self  T Time
K Knowledge  R Relation  Q Quantum/uncertainty  F Faith  C Coherence
```
Example: `G2 M1 E0 S0 T2 K3 R1 Q0 F1 C2` → a strong Knowledge file with grounding,
time, coherence support. Output:
```yaml
primary_factor: K
scores: {G:2, M:1, E:0, S:0, T:2, K:3, R:1, Q:0, F:1, C:2}
secondary_factors: [G, T, C]
entity_guess: LOGOS_INFORMATION
state_guess: W
suggested_filename: K__LOGOS_INFORMATION__W__20260618__LAW06.md
confidence: 0.82
needs_review: true
rename_allowed: false      # supervised until it learns you
```

**Address vs working score:** learn with nuance (0–3), but the stable file
*address* collapses to binary: `0,1 → 0` and `2,3 → 3`. Working score teaches;
address stays stable across AIs.

## Level 3 — Full audit (only when it matters)
Papers, public claims, formal proofs, datasets, dangerous overclaims run the
full `NABLA_CHI_CLASSIFICATION_STANDARD_v1.md`: claim type, assumption load,
attestation, constructive/destructive regime, pressure states, four grades.

## Filing ontology
> Do not file by topic. **File by function inside χ.** Folder = primary χ factor;
> frontmatter = all factors it touches; database/search = the full network.

A file gets ONE primary home even if it touches all ten factors.

## The locked rule
> MEQS begins as a **supervised sorting language, not an autonomous renaming
> authority.** It proposes; you approve; the preference engine learns; only then
> do low-risk types become automatic. `state` and `entity` need your confirmation
> until learned — an **entity registry** (canonical names + aliases) prevents
> name drift. Never permanently move/rename until a file has:
> primary_factor · entity · state · confidence · human_or_learned approval.

## How it plugs into FIS
The χ classifier is an `understand`-stage handler. It emits `primary_factor`,
the 10-factor vector, and a **proposed** MEQS filename — which flows through the
existing propose → authorize → execute pipeline. `rename_allowed:false` keeps it
suggestion-only until approvals train it. Success = "2,000 decisions became 200
easy approvals," not "the computer renamed everything."
