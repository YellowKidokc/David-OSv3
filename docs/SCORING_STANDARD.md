---
title: "Theophysics Scoring Standard v1.0"
uuid: "scoring-standard-001"
date_created: "2026-07-06T00:00:00Z"
status: "canonical"
tags: [system/scoring, system/standard]
purpose: "Canonical reference for the 1-2-3 intensity scoring system applied to all curated pages in the Theophysics vault."
---

# Theophysics Scoring Standard v1.0
## The Tag System

Every curated page gets scored on a fixed set of properties.
Each property receives a score of 1, 2, or 3:

- **3** — Primary feature. This is what the page IS about.
- **2** — Present and meaningful but not dominant.
- **1** — Barely there, mentioned, tangential.
- **0 or omitted** — Not present at all. Leave it out of the YAML.

If you can't decide between 1 and 3, it's a 2. Don't agonize.

---

## Validation Rule

Two independent scorers (any combination of David, AI session, or cold reader)
should produce scores within ±1 of each other on every property. If they diverge
by 2 on any property, the property definition is ambiguous and needs tightening.
Run this test on 5 pages before trusting the system at scale.

---

## Property Set (42 properties, 6 categories)

### WHO — Authorship & Audience

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `AUT` | Author weight | 3=David primary, 2=collaboration, 1=AI-generated |
| `AUD_PHY` | Audience: physicist | 3=written for physicists, 2=accessible to them, 1=incidental |
| `AUD_THE` | Audience: theologian | 3=written for theologians, 2=accessible, 1=incidental |
| `AUD_GEN` | Audience: general | 3=written for general public, 2=accessible, 1=requires expertise |
| `AUD_AI` | Audience: AI | 3=written for AI (like PMM), 2=useful for AI, 1=incidental |

### WHAT — Content Markers

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `SCR` | Scripture content | 3=scripture is load-bearing, 2=referenced, 1=mentioned |
| `EQN` | Equations/math | 3=equations are primary, 2=math supports argument, 1=mentioned |
| `PRF` | Proof | 3=formal proof (Lean or manual), 2=informal proof, 1=implied |
| `NAR` | Narrative/story | 3=narrative-driven, 2=story elements, 1=dry/technical |
| `EXP` | Experimental data | 3=data is primary evidence, 2=data supports, 1=referenced |
| `COD` | Code | 3=code is the deliverable, 2=code supports, 1=code mentioned |
| `VIZ` | Visualization | 3=visual is primary, 2=has visuals, 1=text-only |

### WHEN — Temporal Context

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `ERA` | Historical period | 3=historical context is the argument, 2=history supports, 1=mentioned |
| `EPO` | Framework epoch | 3=current/recent work, 2=mid-period, 1=early/foundational |

### WHERE — Domain Positioning

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `PHY` | Physics | 3=physics is primary domain, 2=physics supports, 1=physics touched |
| `THE` | Theology | 3=theology is primary, 2=theology supports, 1=touched |
| `MAT` | Mathematics | 3=math is primary, 2=math supports, 1=touched |
| `CON` | Consciousness | 3=consciousness is primary, 2=supports, 1=touched |
| `INF` | Information theory | 3=info theory primary, 2=supports, 1=touched |
| `PHI` | Philosophy | 3=philosophy primary, 2=supports, 1=touched |
| `HIS` | History | 3=history primary, 2=supports, 1=touched |
| `PRG` | Programming | 3=code/tools primary, 2=implementation, 1=mentioned |
| `ART` | Artifacts/creative | 3=creative output primary, 2=creative elements, 1=minimal |
| `CAN` | Canonical/framework | 3=defines framework structure, 2=extends framework, 1=uses framework |
| `MOR` | Moral/ethical | 3=moral argument primary, 2=moral implications, 1=touched |
| `EMP` | Experimental/empirical | 3=empirical data primary, 2=data supports, 1=referenced |

### WHY — Rhetorical Method & Intent

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `DER` | Derivation | 3=page IS a derivation, 2=derives something, 1=references derivation |
| `FAL` | Falsification | 3=falsification attempt is primary, 2=tests something, 1=mentions |
| `ELM` | Elimination (7Q) | 3=systematic elimination, 2=eliminates options, 1=references |
| `ANA` | Analogy | 3=analogy-driven, 2=uses analogy, 1=brief comparison |
| `ISO` | Isomorphism | 3=structural bridge is the point, 2=bridge supports, 1=parallel noted |
| `STE` | Steelman/adversarial | 3=strongest objection is the point, 2=addresses objection, 1=mentions |
| `PER` | Persuasion | 3=explicitly persuasive, 2=makes a case, 1=states position |
| `INT_DEF` | Intent: define | 3=primary purpose is definition, 2=defines something, 1=incidental |
| `INT_BRG` | Intent: bridge | 3=primary purpose is connecting domains, 2=bridges, 1=touches |
| `INT_BRK` | Intent: break | 3=primary purpose is falsification, 2=tests, 1=mentions |

### FRAMEWORK — Theophysics-Specific

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `LAW` | Law number | 1-10 (not intensity-scored, just the number) |
| `SYM` | Symmetry pair | The paired law number (1↔8, 2↔9, 3↔10, 4↔7, 5↔6) |
| `CHI_G` | χ: Grace/Negentropy | 1-2-3 intensity |
| `CHI_M` | χ: Mutual Information | 1-2-3 |
| `CHI_E` | χ: Entropy | 1-2-3 |
| `CHI_S` | χ: Self-Reference/Soul | 1-2-3 |
| `CHI_T` | χ: Time | 1-2-3 |
| `CHI_K` | χ: Knowledge | 1-2-3 |
| `CHI_R` | χ: Relationality | 1-2-3 |
| `CHI_Q` | χ: Quantum | 1-2-3 |
| `CHI_F` | χ: Force/Faith | 1-2-3 |
| `CHI_C` | χ: Coherence | 1-2-3 |

### BIBLE — Scripture Layer

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `BIB_OT` | Old Testament | 3=OT is primary source, 2=OT referenced, 1=touched |
| `BIB_NT` | New Testament | 3=NT is primary source, 2=NT referenced, 1=touched |
| `BIB_NAR` | Biblical narrative | 3=narrative arc is the structure, 2=narrative referenced, 1=incidental |

### STATUS — Lifecycle

| Code | Property | Scoring Guide |
|------|----------|---------------|
| `CONF` | Confidence | 3=high confidence, 2=moderate, 1=speculative |
| `TIER` | Classification tier | 1-5 from Theophysics classification system |

---

## YAML Template

Copy this block into any curated page's frontmatter.
Delete properties that score 0 (not present). Keep it clean.

```yaml
---
title: ""
uuid: ""
date_created: ""
status: "draft"
classification: ""
scores:
  # WHO
  AUT: 3
  AUD_PHY: 0
  AUD_THE: 0
  AUD_GEN: 0
  AUD_AI: 0
  # WHAT
  SCR: 0
  EQN: 0
  PRF: 0
  NAR: 0
  EXP: 0
  COD: 0
  VIZ: 0
  # WHEN
  ERA: 0
  EPO: 0
  # WHERE
  PHY: 0
  THE: 0
  MAT: 0
  CON: 0
  INF: 0
  PHI: 0
  HIS: 0
  PRG: 0
  ART: 0
  CAN: 0
  MOR: 0
  EMP: 0
  # WHY
  DER: 0
  FAL: 0
  ELM: 0
  ANA: 0
  ISO: 0
  STE: 0
  PER: 0
  INT_DEF: 0
  INT_BRG: 0
  INT_BRK: 0
  # BIBLE
  BIB_OT: 0
  BIB_NT: 0
  BIB_NAR: 0
  # STATUS
  CONF: 0
  TIER: 0
# FRAMEWORK (include only what applies)
law: null
sym: null
chi_scores:
  G: 0
  M: 0
  E: 0
  S: 0
  T: 0
  K: 0
  R: 0
  Q: 0
  F: 0
  C: 0
# CONNECTIONS
parent: ""
depends_on: []
extends: []
contradicts: []
validates: []
scripture_refs: []
biblical_narrative: ""
---
```

---

## Dataview Queries

### All pages scored 3 on both Physics and Theology (the cross-domain core)
```dataview
TABLE scores.PHY AS "PHY", scores.THE AS "THE", scores.EQN AS "EQN",
      scores.CONF AS "Conf", classification
FROM ""
WHERE scores.PHY = 3 AND scores.THE = 3
SORT scores.CONF DESC
```

### Heavy scripture + heavy equations (the bridge pages)
```dataview
TABLE scores.SCR AS "SCR", scores.EQN AS "EQN", scores.ISO AS "ISO",
      law AS "Law", classification
FROM ""
WHERE scores.SCR >= 2 AND scores.EQN >= 2
SORT scores.ISO DESC
```

### Unexplored high-confidence pages
```dataview
TABLE scores.CONF AS "Conf", scores.TIER AS "Tier", classification,
      scores.PHY AS "PHY", scores.THE AS "THE"
FROM ""
WHERE scores.CONF = 3 AND !contains(file.path, "_EXPLORATIONS")
SORT scores.TIER ASC
```

### Pages by Law with full score profile
```dataview
TABLE law AS "Law", sym AS "Sym", scores.PHY AS "PHY", scores.THE AS "THE",
      scores.MAT AS "MAT", scores.MOR AS "MOR", scores.EQN AS "EQN",
      scores.SCR AS "SCR", scores.CONF AS "Conf"
FROM ""
WHERE law != null
SORT law ASC
```

### Falsification attempts (all BREAK explorations)
```dataview
TABLE scores.FAL AS "FAL", scores.CONF AS "Conf", scores.PHY AS "PHY",
      parent AS "Parent"
FROM "_EXPLORATIONS"
WHERE scores.FAL >= 2
SORT scores.CONF DESC
```

### Intent: Bridge pages (cross-domain connectors)
```dataview
TABLE scores.INT_BRG AS "Bridge", scores.ISO AS "ISO",
      scores.PHY AS "PHY", scores.THE AS "THE", scores.MAT AS "MAT"
FROM ""
WHERE scores.INT_BRG >= 2
SORT scores.ISO DESC
```

---

## Inter-Rater Reliability Test

To validate the scoring system:

1. Pick 5 curated pages (mix of axioms, papers, explorations)
2. Score each page independently (David scores, AI scores)
3. Compare property by property
4. Any property where scores diverge by ≥2 = ambiguous definition
5. Tighten the property definition and re-test
6. System is validated when all 5 pages converge within ±1

---

*Scoring Standard v1.0 | July 6, 2026 | David Lowe / Opus*
