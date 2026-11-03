# Theophysics Corpus Nomenclature Registry

**Scope:** every short code, status letter, classification rule, and naming pattern accrued for the Lean 4 corpus index and the Master Equation claim ledger.  
**Maintained in:** `D:\GitHub\David-OSv3\LEAN 4\theophysics_corpus_indexer\NOMENCLATURE.md`  
**Synced to:** `\\192.168.2.50\h_hp\Desktop\theophysics_corpus_indexer\NOMENCLATURE.md` and the FIS sidecar archive.

---

## 1. Prime directives (these shape all naming)

1. **READ-ONLY on source folders.** Copy, never move/delete/edit a source.
2. **SHA-256 is the primary key.** Same bytes = same record.
3. **Verification levels are separate facts**, never blended into one flag.
4. **Classification is derived from file content** (declarations), never trusted from filename/folder/header.
5. **Every run writes a receipt.** No silent success.

---

## 2. Verification levels

Stored in `files.verif_level`. Computed from receipts, never hand-set.

| Level | Rule |
|-------|------|
| `KERNEL` | BUILD receipt shows pass + `PRINT_AXIOMS` is clean of `native_decide` |
| `KERNEL_NATIVE_DECIDE` | BUILD pass + `native_decide` present in print output |
| `AI_REVIEW` | Only an `AI_REVIEW` receipt exists |
| `GAPS` | `sorry_active > 0` |
| `UNVERIFIED` | Default; none of the above apply |

---

## 3. Series taxonomy (corpus classifier labels)

One label per file in `files.series`. Used for the whole vault.

| Series | Meaning |
|--------|---------|
| `MASTER_EQUATION` | Governing equation, coherence algebra, operator/law material |
| `AXIOMS` | Foundational axioms / primitive claims |
| `SPIRITUAL_TERMS` | Fruit/agape/joy/peace/justice/mercy etc. |
| `TEN_LAWS` | Law expansions, force names, thermodynamics |
| `TRINITY` | Trinity / perichoresis material |
| `GRACE_COHERENCE` | Grace, coherence, repair, restoration, Lindblad |
| `FALL_ENTROPY` | Fall, entropy, fracture, decay, sin_ |
| `GENESIS_QUANTUM` | Genesis / quantum bridge material |
| `HARNESS_TESTS` | Tests, harnesses, adversarial / counter-example work |
| `LIBRARY` | Mathlib / toolchain; `is_library = true` |

### Classification order v1 (first match wins)

Applied from `.lean` declarations only; comments/strings masked.

1. `LIBRARY`: any declaration/import matching Mathlib names (`Mathlib.`, `RiemannZeta`, `TopologicalSpace`, `Finsupp`, `Etale`, `EssSup`, `RefinedDiscrTree`, `Hilbert90`, `DefEqTransformations`, or path segment `Mathlib`). Stop.
2. `TRINITY`: `trinity|triune|perichor`
3. `MASTER_EQUATION`: `chi|listProd|MasterState|CoherenceAlgebra|CoherenceOperator|LawIso|LawModel`
4. `GRACE_COHERENCE`: `grace|coherence|repair|restor|lindblad`
5. `FALL_ENTROPY`: `fall|entropy|fracture|decay|sin_`
6. `TEN_LAWS`: `law[0-9]|tenlaw|weak_force|strong_force|electromag|thermodynam`
7. `SPIRITUAL_TERMS`: `fruit|agape|joy_|peace_|patience|kindness|justice|mercy|faith_`
8. `AXIOMS`: `axiom|jenga|divine_order|god_is|primitive`
9. `HARNESS_TESTS`: `test_|harness|adversarial|counterexample|control_`
10. else `NULL` (unclassified)

---

## 4. Corpus sidecar short codes

Namespace prefix: `L4` = the Lean 4 corpus namespace.

| Code | View | Manifest | Meaning |
|------|------|----------|---------|
| `L4` | — | — | Lean 4 corpus namespace overall |
| `QRN` | `l4_qrn` | `L4_QRN.csv` | Quarantine: `is_library = true` |
| `UNC` | `l4_unc` | `L4_UNC.csv` | Unclassified: `series IS NULL` |
| `DUP` | `l4_dup` | `L4_DUP.csv` | Duplicates: one SHA-256 at >1 location |

Manifests live in `\\192.168.2.50\h_hp\Desktop\REVIEW\`.

---

## 5. Master Equation (ME) namespace

Coordinate order: **`ME.<status>.<kind>`**

- `ME` = Master Equation claim/convergence space
- `<status>` = one-letter status (see §5.1)
- `<kind>` = three-letter kind code (see §5.2)

### 5.1 Status letters

| Letter | Word | Meaning |
|--------|------|---------|
| `U` | `UNREVIEWED` | Routed and classified; no judgment yet |
| `P` | `PROVEN` | Ruled proven |
| `B` | `BELIEVED-UNPROVEN` | Believed but not proven |
| `D` | `DISPROVEN` | Ruled disproven |
| `X` | `CONTESTED` | Under cross-examination / unresolved tension |
| `K` | `CORE` | The promoted governing claim |

`K` is reserved for the governing claim. Everything else starts as `U`.

### 5.2 Kind codes

Derived from the existing folder structure under `04_MASTER_EQUATION`.

| Code | Source folder | Use |
|------|---------------|-----|
| `DEF` | `00_EQUATION_DEFINITION_BOOK` | Equation definitions |
| `LAW` | `020_LAW_EXPANSIONS` | Governed laws |
| `DER` | *(split out from law/audit work)* | A claimed derivation path to a law |
| `TST` | `025_CANONICAL_TESTS` | Canonical tests |
| `SPI` | `030_SPIRITUAL_TERMS` | Spiritual terms |
| `PHY` | `040_PHYSICAL_TERMS` | Physical terms |
| `PRF` | `050_LEAN_PROOFS` | Lean proofs (also used for corpus files classified `MASTER_EQUATION`) |
| `MTB` | `050_MATH_TRANSLATION_BLOCKS` | Math translation blocks |
| `AUD` | `055_MATHEMATICAL_AUDIT_AND_EXTENSIONS` | Audit / extensions |
| `RET` | `060_MISTAKES_RETIRED_FORMS` | Retired / mistake forms |
| `RCP` | `070_LEAN_RECEIPTS` | Build / print receipts |
| `WEB` | `080_HTML_BLOCK_SPECS` | HTML / web block specs |
| `INT` | `090_INTAKE_LEDGERS` | Intake ledgers |
| `HIS` | `015_HISTORICAL_ARCS` | Historical arcs |
| `HUB` | `010_MAIN_INTRO_AND_HUB` | Main intro / hub |
| `STH` | `000_START_HERE` | Start-here material |
| `ARC` | `999_ARCHIVE_SOURCE_COPIES` | Archive source copies |

### 5.3 Master Equation sidecar tables

- `me_claims` — governing claim record (`claim_id = 'ME'`, status `K`)
- `me_presentations` — every file pinned to the claim
- `me_drift` — rows where a non-K presentation has `pinned_version != claim.statement_version`
- `me_claim_receipts` — claim-level receipts (rulings, AI co-sign, drift checks)

### 5.4 Statement version rule

`statement_version` = first 16 characters of the canonical document's SHA-256.

### 5.5 Canonical document selection

Latest-modified file matching `THE_MASTER_EQUATION_CANONICAL_DOCUMENT*.md` under `C:\Users\David\Documents\faiththruphysics.com\04_MASTER_EQUATION`.

### 5.6 Law ordering authority

The Aug 9 ruled eponym dictionary (`04_MASTER_EQUATION\...\90_SOURCE_MAP\SELECTED_CURRENT_SOURCES\THE_MASTER_EQUATION_CANONICAL_DOCUMENT.md`) is the **only** authority for law names/ordering:

- Law 2 = Newton-Momentum / Sin Nature-Repentance  
  *(NOT Einstein-Meaning)*
- Law 9 = Moral Conservation  
  *(NOT Sin/Decay)*
- C/Law 10 = operator wrapper, never a tenth product factor

---

## 6. Receipt naming

Receipts live in `<project>\receipts\`.

Pattern: `<run-id>-receipt.json`

Examples:
- `reclassify-2026-09-22T173406-receipt.json`
- `me-sidecar-2026-09-22T181656-receipt.json`

Every receipt must include counts, timestamps, config hash, and the exact query used for any export.

---

## 7. Three-coordinate naming convention (project-wide)

The pattern that keeps appearing:

> **Category → Status → Kind**

Examples:
- Corpus sidecar: `L4.QRN`, `L4.UNC`, `L4.DUP`
- Master Equation: `ME.K.LAW`, `ME.U.DEF`, `ME.X.DER`
- Claim records: series + status + grade

A file encoded this way would look like:

```
ME.K.LAW.md
ME.U.DER.lean
L4.UNC.txt
```

The three coordinates are the canonical classification layer; physical folders are a render choice, not the source of truth.

---

## 8. Change log

| Date | Change |
|------|--------|
| 2026-09-22 | Initial registry: L4/QRN/UNC/DUP sidecars, ME namespace, status letters, kind codes, classification rules v1, receipt naming, three-coordinate convention. |

---

## 9. How to update this file

1. Edit `D:\GitHub\David-OSv3\LEAN 4\theophysics_corpus_indexer\NOMENCLATURE.md`.
2. Add a row to the change log.
3. Copy to `\\192.168.2.50\h_hp\Desktop\theophysics_corpus_indexer\NOMENCLATURE.md`.
4. Copy to `D:\GitHub\David-OSv3\_FIS_ROOT_SIDECAR_ARCHIVE\EVIDENCE\sidecar_corpus_indexer\theophysics_corpus_indexer\NOMENCLATURE.md`.
