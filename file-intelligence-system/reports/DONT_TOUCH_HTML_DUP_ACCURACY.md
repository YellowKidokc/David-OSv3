# Duplicate accuracy packet — DONT TOUCH HTML series
Generated: 2026-08-19T04:28:08+00:00
Roots: `HTML/` · `MD/` · `Canon/`  (skipped `_deploy*`, `_lineage*`, `.wrangler`, assets)
Method: strip nav/header/footer/script/style, then SHA of remaining text **and** Jaccard on unique words.
Nothing was renamed or moved.

- Files scanned: **280**
- Exact core-text groups: **7** (byte-identical after shell strip)
- Cross-folder exact: **1**
- Same-folder exact: **6**
- Same-stem pairs scored: **94**
  - near-identical (≥0.97): **57**
  - format/wrapper twin (0.90–0.97): **12**
  - same article, edited (0.70–0.90): **13**
  - related name, different body (<0.70): **12**

## How to read this

Exact SHA is strict: one extra topbar word fails it. Jaccard is the accuracy check.
High Jaccard + different SHA = the duplicates you already know are there; the files are format twins, not unique essays.

## Same-stem closeness

| Stem | A | B | Jaccard | Words | Verdict |
|---|---|---|---:|---|---|
| `02-the-trinity-signature` | `HTML\02-the-trinity-signature.html` | `MD\02-the-trinity-signature.md` | 1.000 | 2980 / 2980 | near-identical |
| `02-the-trinity-signature` | `HTML\02-the-trinity-signature.html` | `Canon\02-the-trinity-signature.canonical.md` | 1.000 | 2980 / 2966 | near-identical |
| `02-the-trinity-signature` | `MD\02-the-trinity-signature.md` | `Canon\02-the-trinity-signature.canonical.md` | 1.000 | 2980 / 2966 | near-identical |
| `04-you-are-god-story-told-through-physics` | `HTML\04-you-are-god-story-told-through-physics.html` | `MD\04-you-are-god-story-told-through-physics.md` | 1.000 | 2445 / 2444 | near-identical |
| `grace-modes` | `HTML\grace-modes-8efc21c7.html` | `HTML\grace-modes.html` | 1.000 | 1241 / 1241 | near-identical |
| `review_first` | `HTML\REVIEW_FIRST-319d177f.html` | `HTML\REVIEW_FIRST.html` | 1.000 | 208 / 208 | near-identical |
| `13-be-fruitful-and-multiply` | `HTML\13-be-fruitful-and-multiply.html` | `Canon\13-be-fruitful-and-multiply.html` | 0.999 | 1913 / 1916 | near-identical |
| `11-the-moral-first-chain` | `HTML\11-the-moral-first-chain.html` | `Canon\11-the-moral-first-chain.html` | 0.998 | 1541 / 1544 | near-identical |
| `01-trinity-chain` | `MD\01-trinity-chain.md` | `Canon\01-trinity-chain.canonical.md` | 0.997 | 2401 / 2394 | near-identical |
| `03-three-body-solution` | `HTML\03-three-body-solution.html` | `Canon\03-three-body-solution.html` | 0.997 | 2763 / 2766 | near-identical |
| `02-the-trinity-signature` | `HTML\02-the-trinity-signature.html` | `Canon\02-the-trinity-signature.html` | 0.997 | 2980 / 2989 | near-identical |
| `02-the-trinity-signature` | `MD\02-the-trinity-signature.md` | `Canon\02-the-trinity-signature.html` | 0.997 | 2980 / 2989 | near-identical |
| `02-the-trinity-signature` | `Canon\02-the-trinity-signature.canonical.md` | `Canon\02-the-trinity-signature.html` | 0.997 | 2966 / 2989 | near-identical |
| `11-the-moral-first-chain` | `HTML\11-the-moral-first-chain.html` | `Canon\11-the-moral-first-chain.canonical.md` | 0.997 | 1541 / 1530 | near-identical |
| `02-the-shadow` | `HTML\02-the-shadow.html` | `Canon\02-the-shadow.canonical.md` | 0.996 | 1627 / 1619 | near-identical |
| `01-trinity-chain` | `HTML\01-trinity-chain.html` | `Canon\01-trinity-chain.html` | 0.996 | 2834 / 2837 | near-identical |
| `w1.2-why-god-built-physics` | `Canon\W1.2-why-god-built-physics.canonical.md` | `Canon\W1.2-why-god-built-physics.html` | 0.996 | 3715 / 3724 | near-identical |
| `w1.1-you-are-god` | `Canon\W1.1-you-are-god.canonical.md` | `Canon\W1.1-you-are-god.html` | 0.996 | 3701 / 3711 | near-identical |
| `12-the-is-ought-dissolution` | `HTML\12-the-is-ought-dissolution.html` | `Canon\12-the-is-ought-dissolution.html` | 0.995 | 1729 / 1737 | near-identical |
| `consciousness-chain` | `HTML\consciousness-chain.html` | `Canon\consciousness-chain.html` | 0.995 | 1939 / 1942 | near-identical |
| `11-the-moral-first-chain` | `Canon\11-the-moral-first-chain.canonical.md` | `Canon\11-the-moral-first-chain.html` | 0.995 | 1530 / 1544 | near-identical |
| `02-the-shadow` | `HTML\02-the-shadow.html` | `Canon\02-the-shadow.html` | 0.995 | 1627 / 1630 | near-identical |
| `character-of-god-from-physics` | `HTML\character-of-god-from-physics.html` | `Canon\character-of-god-from-physics.html` | 0.994 | 2570 / 2579 | near-identical |
| `w1.3-the-plus-sign` | `Canon\W1.3-the-plus-sign.canonical.md` | `Canon\W1.3-the-plus-sign.html` | 0.994 | 1555 / 1567 | near-identical |
| `09-the-ledger` | `HTML\09-the-ledger.html` | `MD\09-the-ledger.md` | 0.993 | 2295 / 2311 | near-identical |
| `w7.6-how-claims-live-and-die` | `Canon\W7.6-how-claims-live-and-die.canonical.md` | `Canon\W7.6-how-claims-live-and-die.html` | 0.993 | 2027 / 2041 | near-identical |
| `08-the-bridge` | `HTML\08-the-bridge.html` | `MD\08-the-bridge.md` | 0.993 | 928 / 966 | near-identical |
| `w7.3-the-lean-survivors` | `Canon\W7.3-the-lean-survivors.canonical.md` | `Canon\W7.3-the-lean-survivors.html` | 0.993 | 1402 / 1414 | near-identical |
| `w7.5-the-ledger` | `Canon\W7.5-the-ledger.canonical.md` | `Canon\W7.5-the-ledger.html` | 0.993 | 2230 / 2243 | near-identical |
| `03-the-cost` | `HTML\03-the-cost.html` | `Canon\03-the-cost.html` | 0.993 | 1319 / 1322 | near-identical |
| `w7.2-the-verification` | `Canon\W7.2-the-verification.canonical.md` | `Canon\W7.2-the-verification.html` | 0.992 | 1339 / 1350 | near-identical |
| `03-three-body-solution` | `MD\03-three-body-solution.md` | `Canon\03-three-body-solution.canonical.md` | 0.992 | 1595 / 1588 | near-identical |
| `02-the-shadow` | `Canon\02-the-shadow.canonical.md` | `Canon\02-the-shadow.html` | 0.991 | 1619 / 1630 | near-identical |
| `w0.1-start-here` | `Canon\W0.1-start-here.canonical.md` | `Canon\W0.1-start-here.html` | 0.991 | 1955 / 1977 | near-identical |
| `12-the-is-ought-dissolution` | `HTML\12-the-is-ought-dissolution.html` | `Canon\12-the-is-ought-dissolution.canonical.md` | 0.991 | 1729 / 1707 | near-identical |
| `w2.5-why-not-otherwise` | `Canon\W2.5-why-not-otherwise.canonical.md` | `Canon\W2.5-why-not-otherwise.html` | 0.991 | 1237 / 1211 | near-identical |
| `character-of-god-from-physics` | `HTML\character-of-god-from-physics.html` | `Canon\character-of-god-from-physics.canonical.md` | 0.990 | 2570 / 2553 | near-identical |
| `w2.3-four-axioms` | `Canon\W2.3-four-axioms.canonical.md` | `Canon\W2.3-four-axioms.html` | 0.989 | 1068 / 1078 | near-identical |
| `w0.2-god-in-the-equations` | `Canon\W0.2-god-in-the-equations.canonical.md` | `Canon\W0.2-god-in-the-equations.html` | 0.989 | 2167 / 2181 | near-identical |
| `13-be-fruitful-and-multiply` | `HTML\13-be-fruitful-and-multiply.html` | `Canon\13-be-fruitful-and-multiply.canonical.md` | 0.988 | 1913 / 1900 | near-identical |
| `w5-consciousness-mirror` | `Canon\W5-consciousness-mirror.canonical.md` | `Canon\W5-consciousness-mirror.html` | 0.988 | 6182 / 6242 | near-identical |
| `w3.4-portrait` | `Canon\W3.4-portrait.canonical.md` | `Canon\W3.4-portrait.html` | 0.987 | 4986 / 5008 | near-identical |
| `13-be-fruitful-and-multiply` | `Canon\13-be-fruitful-and-multiply.canonical.md` | `Canon\13-be-fruitful-and-multiply.html` | 0.987 | 1900 / 1916 | near-identical |
| `12-the-is-ought-dissolution` | `Canon\12-the-is-ought-dissolution.canonical.md` | `Canon\12-the-is-ought-dissolution.html` | 0.986 | 1707 / 1737 | near-identical |
| `w8.1-what-if-we-measured-the-wrong-thing` | `Canon\W8.1-what-if-we-measured-the-wrong-thing.canonical.md` | `Canon\W8.1-what-if-we-measured-the-wrong-thing.html` | 0.986 | 1200 / 1216 | near-identical |
| `character-of-god-from-physics` | `Canon\character-of-god-from-physics.canonical.md` | `Canon\character-of-god-from-physics.html` | 0.985 | 2553 / 2579 | near-identical |
| `w3.5-law-1` | `Canon\W3.5-law-1-canonical.canonical.md` | `Canon\W3.5-law-1-canonical.html` | 0.984 | 1580 / 1602 | near-identical |
| `w2.4-finitude` | `Canon\W2.4-finitude.canonical.md` | `Canon\W2.4-finitude.html` | 0.981 | 2353 / 2371 | near-identical |
| `w7-blue-sheet-tp00` | `Canon\W7-blue-sheet-tp00.canonical.md` | `Canon\W7-blue-sheet-tp00.html` | 0.981 | 803 / 812 | near-identical |
| `w2.6-the-descent` | `Canon\W2.6-the-descent.canonical.md` | `Canon\W2.6-the-descent.html` | 0.979 | 1299 / 1334 | near-identical |
| `family-00-start-here` | `HTML\FAMILY-00-start-here.html` | `MD\FAMILY-00-start-here.md` | 0.979 | 1976 / 2024 | near-identical |
| `w3-master-equation` | `Canon\W3-master-equation.canonical.md` | `Canon\W3-master-equation.html` | 0.977 | 5164 / 5249 | near-identical |
| `w2.2-single-expression` | `Canon\W2.2-single-expression.canonical.md` | `Canon\W2.2-single-expression.html` | 0.976 | 1200 / 1233 | near-identical |
| `w8.4-derivation-grammar` | `Canon\W8.4-derivation-grammar.canonical.md` | `Canon\W8.4-derivation-grammar.html` | 0.976 | 1365 / 1383 | near-identical |
| `sci-00-the-science-argument-for-triadic-structure` | `HTML\SCI-00-the-science-argument-for-triadic-structure.html` | `MD\SCI-00-the-science-argument-for-triadic-structure.md` | 0.975 | 4907 / 4791 | near-identical |
| `w1.4-god-in-the-gaps` | `Canon\W1.4-god-in-the-gaps.canonical.md` | `Canon\W1.4-god-in-the-gaps.html` | 0.970 | 2058 / 2072 | near-identical |
| `w7.4-the-lagrangian` | `Canon\W7.4-the-lagrangian.canonical.md` | `Canon\W7.4-the-lagrangian.html` | 0.970 | 1046 / 1063 | near-identical |
| `w2.1-part-zero` | `Canon\W2.1-part-zero.canonical.md` | `Canon\W2.1-part-zero.html` | 0.970 | 2513 / 2560 | format/wrapper twin |
| `03-the-master-equation` | `HTML\03-the-master-equation.html` | `MD\03-the-master-equation.md` | 0.967 | 1027 / 1033 | format/wrapper twin |
| `06-the-ten-laws` | `HTML\06-the-ten-laws-canonical.html` | `MD\06-the-ten-laws-canonical.md` | 0.967 | 3266 / 3254 | format/wrapper twin |
| `w8.3-axiom-gap-fill` | `Canon\W8.3-axiom-gap-fill.canonical.md` | `Canon\W8.3-axiom-gap-fill.html` | 0.965 | 926 / 949 | format/wrapper twin |
| `w2.7-the-bridge` | `Canon\W2.7-the-bridge.canonical.md` | `Canon\W2.7-the-bridge.html` | 0.962 | 1038 / 1096 | format/wrapper twin |
| `w7.8-the-7q-universal-classifier` | `Canon\W7.8-the-7q-universal-classifier.canonical.md` | `Canon\W7.8-the-7q-universal-classifier.html` | 0.945 | 1657 / 1701 | format/wrapper twin |
| `w7.1-the-honest-fight` | `Canon\W7.1-the-honest-fight.canonical.md` | `Canon\W7.1-the-honest-fight.html` | 0.944 | 1215 / 1244 | format/wrapper twin |
| `w4-trinity-t02` | `Canon\W4-trinity-t02.canonical.md` | `Canon\W4-trinity-t02.html` | 0.937 | 5692 / 6120 | format/wrapper twin |
| `w3.3-the-math` | `Canon\W3.3-the-math.canonical.md` | `Canon\W3.3-the-math.html` | 0.937 | 1707 / 1881 | format/wrapper twin |
| `07-spiritual-terms` | `HTML\07-spiritual-terms.html` | `MD\07-spiritual-terms.md` | 0.925 | 3590 / 3553 | format/wrapper twin |
| `05-the-descent` | `HTML\05-the-descent.html` | `MD\05-the-descent.md` | 0.906 | 1309 / 1296 | format/wrapper twin |
| `w8.2-templeton-dossier` | `Canon\W8.2-templeton-dossier.canonical.md` | `Canon\W8.2-templeton-dossier.html` | 0.902 | 717 / 760 | format/wrapper twin |
| `consciousness-chain` | `HTML\consciousness-chain.html` | `Canon\consciousness-chain.canonical.md` | 0.886 | 1939 / 1617 | same article, edited |
| `04-the-ten-laws` | `HTML\04-the-ten-laws-672b6573.html` | `HTML\04-the-ten-laws.html` | 0.883 | 1465 / 1728 | same article, edited |
| `consciousness-chain` | `Canon\consciousness-chain.canonical.md` | `Canon\consciousness-chain.html` | 0.882 | 1617 / 1942 | same article, edited |
| `01-trinity-chain` | `HTML\01-trinity-chain.html` | `Canon\01-trinity-chain.canonical.md` | 0.880 | 2834 / 2394 | same article, edited |
| `01-trinity-chain` | `HTML\01-trinity-chain.html` | `MD\01-trinity-chain.md` | 0.878 | 2834 / 2401 | same article, edited |
| `01-trinity-chain` | `Canon\01-trinity-chain.canonical.md` | `Canon\01-trinity-chain.html` | 0.877 | 2394 / 2837 | same article, edited |
| `01-trinity-chain` | `MD\01-trinity-chain.md` | `Canon\01-trinity-chain.html` | 0.875 | 2401 / 2837 | same article, edited |
| `00-god` | `HTML\00-god-index.html` | `MD\00-god-index.md` | 0.831 | 688 / 1072 | same article, edited |
| `w7.9-science-argument-triadic-structure` | `Canon\W7.9-science-argument-triadic-structure.canonical.md` | `Canon\W7.9-science-argument-triadic-structure.html` | 0.818 | 1970 / 2086 | same article, edited |
| `unified_derivation_grammar_v0.2` | `HTML\Unified_Derivation_Grammar_v0.2.html` | `MD\Unified_Derivation_Grammar_v0.2.md` | 0.798 | 2534 / 2267 | same article, edited |
| `03-the-master-equation` | `HTML\03-the-master-equation-a6740e89.html` | `HTML\03-the-master-equation.html` | 0.791 | 1332 / 1027 | same article, edited |
| `03-the-master-equation` | `HTML\03-the-master-equation-a6740e89.html` | `MD\03-the-master-equation.md` | 0.777 | 1332 / 1033 | same article, edited |
| `unified_derivation_grammar_v0.1` | `HTML\Unified_Derivation_Grammar_v0.1.html` | `MD\Unified_Derivation_Grammar_v0.1.md` | 0.707 | 3204 / 2167 | same article, edited |
| `03-three-body-solution` | `HTML\03-three-body-solution.html` | `Canon\03-three-body-solution.canonical.md` | 0.690 | 2763 / 1588 | related name, different body |
| `03-three-body-solution` | `Canon\03-three-body-solution.canonical.md` | `Canon\03-three-body-solution.html` | 0.688 | 1588 / 2766 | related name, different body |
| `03-three-body-solution` | `HTML\03-three-body-solution.html` | `MD\03-three-body-solution.md` | 0.686 | 2763 / 1595 | related name, different body |
| `03-three-body-solution` | `MD\03-three-body-solution.md` | `Canon\03-three-body-solution.html` | 0.684 | 1595 / 2766 | related name, different body |
| `03-the-cost` | `HTML\03-the-cost.html` | `Canon\03-the-cost.canonical.md` | 0.676 | 1319 / 728 | related name, different body |
| `03-the-cost` | `Canon\03-the-cost.canonical.md` | `Canon\03-the-cost.html` | 0.671 | 728 / 1322 | related name, different body |
| `spiritual-terms` | `HTML\spiritual-terms-e8047e43.html` | `HTML\spiritual-terms.html` | 0.347 | 3590 / 865 | related name, different body |
| `the-descent` | `HTML\the-descent-41416f4e.html` | `HTML\the-descent.html` | 0.332 | 1309 / 327 | related name, different body |
| `05-the-plan-a-cost` | `MD\05-the-plan-a-cost-ffaf118f.md` | `MD\05-the-plan-a-cost.md` | 0.278 | 1036 / 1696 | related name, different body |
| `consciousness_lean_targets` | `MD\CONSCIOUSNESS_LEAN_TARGETS.md` | `MD\CONSCIOUSNESS_LEAN_TARGETS_V2.md` | 0.190 | 438 / 656 | related name, different body |
| `review_first` | `HTML\REVIEW_FIRST-319d177f.html` | `Canon\REVIEW_FIRST.html` | 0.136 | 208 / 430 | related name, different body |
| `review_first` | `HTML\REVIEW_FIRST.html` | `Canon\REVIEW_FIRST.html` | 0.136 | 208 / 430 | related name, different body |

## Cross-folder exact SHA

### `acba65d2502c0642`  (2 files · HTML,MD)
- `HTML\Audit of the Theophysics workbook stack.html` — 4961 words, 39,148 bytes
- `MD\AUDIT-00-theophysics-workbook-stack.md` — 4961 words, 39,148 bytes

## Same-folder exact SHA

- `8c90c2a97feba133`
  - `HTML\05-the-descent.html`
  - `HTML\the-descent-41416f4e.html`
- `8fa57d70b23dc998`
  - `HTML\07-spiritual-terms.html`
  - `HTML\spiritual-terms-e8047e43.html`
- `a33ad1ad29a18580`
  - `HTML\Consciousness.html`
  - `HTML\Sheet_L3_Consciousness.html`
  - `HTML\Sheet_L3_Consciousness_1.html`
- `452afd863c360694`
  - `HTML\grace-modes-8efc21c7.html`
  - `HTML\grace-modes.html`
  - `HTML\MASTER_DERIVATION_ATLAS.html`
- `deb33ba57175f4ee`
  - `HTML\l3 consciousness.HTML`
  - `HTML\Sheet g derivation.HTML`
  - `HTML\Sheet_L3_Consciousness_2.html`
- `d35cd07e9807323a`
  - `HTML\REVIEW_FIRST-319d177f.html`
  - `HTML\REVIEW_FIRST.html`

## Per-file index

| Bucket | Stem | Core | Words | Path |
|---|---|---|---:|---|
| HTML | `00` | `eee79b60ba0a1aea` | 583 | `HTML\00-index.html` |
| HTML | `00-audit-workbook-stack` | `f083fd0593dd8f28` | 4924 | `HTML\00-audit-workbook-stack.html` |
| HTML | `00-god` | `069dd38a3506cb61` | 688 | `HTML\00-god-index.html` |
| MD | `00-god` | `c2247fdfc75d50cf` | 1072 | `MD\00-god-index.md` |
| HTML | `00-index_1` | `f1a09a53517ce9ca` | 447 | `HTML\00-index_1.html` |
| HTML | `00-part-zero` | `b3f9a80ad388367b` | 2449 | `HTML\00-part-zero.html` |
| HTML | `00-review` | `9f96eead2473c8ed` | 437 | `HTML\00-review-index.html` |
| HTML | `001-the-single-expression` | `8d9bc97afde4bee5` | 1405 | `HTML\001-the-single-expression.html` |
| HTML | `00a-the-four-axioms` | `860effd2942e51d4` | 1155 | `HTML\00A-the-four-axioms.html` |
| MD | `00a-the-truth-rule` | `fa857b463ffe9c46` | 2217 | `MD\00a-the-truth-rule.md` |
| MD | `01 - family doorway - what david has been building` | `aa64600d9612b97e` | 1543 | `MD\01 - Family Doorway - What David Has Been Building.md` |
| HTML | `01-family-start-here` | `1ecd4379e952aa19` | 1988 | `HTML\01-family-start-here.html` |
| HTML | `01-the-story` | `3fc6064dfd924a02` | 2113 | `HTML\01-the-story.html` |
| Canon | `01-trinity-chain` | `84af817786c33d08` | 2394 | `Canon\01-trinity-chain.canonical.md` |
| Canon | `01-trinity-chain` | `ea1be37d97a3e6f6` | 2837 | `Canon\01-trinity-chain.html` |
| HTML | `01-trinity-chain` | `b6be817850b0248d` | 2834 | `HTML\01-trinity-chain.html` |
| MD | `01-trinity-chain` | `a17de3354a7c6550` | 2401 | `MD\01-trinity-chain.md` |
| Canon | `01_consolidated_04_consciousness` | `81b001046d78e000` | 6795 | `Canon\_source_intake\Consciousness_Packet_20260814\01_CONSOLIDATED_04_CONSCIOUSNESS.md` |
| HTML | `02-the-foundation` | `b7dceab7cc50771e` | 1206 | `HTML\02-the-foundation.html` |
| Canon | `02-the-shadow` | `79be9fdd7c590ce6` | 1619 | `Canon\02-the-shadow.canonical.md` |
| Canon | `02-the-shadow` | `8cf8a91272e147f8` | 1630 | `Canon\02-the-shadow.html` |
| HTML | `02-the-shadow` | `33de2966bc0c18a4` | 1627 | `HTML\02-the-shadow.html` |
| Canon | `02-the-trinity-signature` | `880f428731d3f7d9` | 2966 | `Canon\02-the-trinity-signature.canonical.md` |
| Canon | `02-the-trinity-signature` | `f1189a80d555f5fe` | 2989 | `Canon\02-the-trinity-signature.html` |
| HTML | `02-the-trinity-signature` | `d29350e8430ef9ea` | 2980 | `HTML\02-the-trinity-signature.html` |
| MD | `02-the-trinity-signature` | `1c7706fd2b8ec5d6` | 2980 | `MD\02-the-trinity-signature.md` |
| HTML | `02-theophysics-blue-sheet` | `7515beea0277f94b` | 795 | `HTML\02-theophysics-blue-sheet.html` |
| Canon | `02_page_19_consciousness_placeholder` | `706a06e3831c6137` | 364 | `Canon\_source_intake\Consciousness_Packet_20260814\02_PAGE_19_CONSCIOUSNESS_PLACEHOLDER.md` |
| HTML | `03-science-triadic-structure` | `9ec2627148cb0363` | 4772 | `HTML\03-science-triadic-structure.html` |
| Canon | `03-the-cost` | `94b67643f7c4c3d5` | 728 | `Canon\03-the-cost.canonical.md` |
| Canon | `03-the-cost` | `4614907d643bdb2c` | 1322 | `Canon\03-the-cost.html` |
| HTML | `03-the-cost` | `3edc8b9ff1d874f2` | 1319 | `HTML\03-the-cost.html` |
| HTML | `03-the-master-equation` | `8471247244209e02` | 1332 | `HTML\03-the-master-equation-a6740e89.html` |
| HTML | `03-the-master-equation` | `112677c5cac8f704` | 1027 | `HTML\03-the-master-equation.html` |
| MD | `03-the-master-equation` | `ab95f04af3fd65a5` | 1033 | `MD\03-the-master-equation.md` |
| Canon | `03-three-body-solution` | `9f34a918a3c04b5d` | 1588 | `Canon\03-three-body-solution.canonical.md` |
| Canon | `03-three-body-solution` | `3028e1e33a827535` | 2766 | `Canon\03-three-body-solution.html` |
| HTML | `03-three-body-solution` | `b07ee6151c3be3c6` | 2763 | `HTML\03-three-body-solution.html` |
| MD | `03-three-body-solution` | `3512dc8e554b7fa5` | 1595 | `MD\03-three-body-solution.md` |
| MD | `03_chapter_3` | `0576d310cd067357` | 709 | `MD\03_Chapter_3.md` |
| Canon | `03_personhood_bridge` | `fdecd6c40bb340dc` | 1145 | `Canon\_source_intake\Consciousness_Packet_20260814\03_PERSONHOOD_BRIDGE.md` |
| HTML | `04-the-cost` | `648cce6aa25ca283` | 1388 | `HTML\04-the-cost.html` |
| HTML | `04-the-ten-laws` | `78272c21f61ba489` | 1465 | `HTML\04-the-ten-laws-672b6573.html` |
| HTML | `04-the-ten-laws` | `29ffc28ead13fd20` | 1728 | `HTML\04-the-ten-laws.html` |
| HTML | `04-you-are-god-story-told-through-physics` | `58fe6fd737b51ff3` | 2445 | `HTML\04-you-are-god-story-told-through-physics.html` |
| MD | `04-you-are-god-story-told-through-physics` | `1eb42720d1512ac6` | 2444 | `MD\04-you-are-god-story-told-through-physics.md` |
| Canon | `04_h06_consciousness_and_phi` | `4ea5b9ded6d7191c` | 1709 | `Canon\_source_intake\Consciousness_Packet_20260814\04_H06_CONSCIOUSNESS_AND_PHI.md` |
| HTML | `05-the-derivations` | `7fe43e67d1584970` | 1176 | `HTML\05-the-derivations.html` |
| HTML | `05-the-descent` | `8c90c2a97feba133` | 1309 | `HTML\05-the-descent.html` |
| MD | `05-the-descent` | `209fc2130e91f73b` | 1296 | `MD\05-the-descent.md` |
| MD | `05-the-plan-a-cost` | `da8c16aae07c94c0` | 1036 | `MD\05-the-plan-a-cost-ffaf118f.md` |
| MD | `05-the-plan-a-cost` | `858ed7ea974cb832` | 1696 | `MD\05-the-plan-a-cost.md` |
| HTML | `06-the-honest-fight` | `a8fd2d09992b30a0` | 1191 | `HTML\06-the-honest-fight.html` |
| HTML | `06-the-ten-laws` | `b902fa276e26cb9b` | 3266 | `HTML\06-the-ten-laws-canonical.html` |
| MD | `06-the-ten-laws` | `6b9eb3099c2bf72a` | 3254 | `MD\06-the-ten-laws-canonical.md` |
| HTML | `07-spiritual-terms` | `8fa57d70b23dc998` | 3590 | `HTML\07-spiritual-terms.html` |
| MD | `07-spiritual-terms` | `5c455770c0cbc1c2` | 3553 | `MD\07-spiritual-terms.md` |
| HTML | `07-the-verification` | `2a708c22c7868719` | 1421 | `HTML\07-the-verification.html` |
| HTML | `08-the-bridge` | `038ccf33de2eee0b` | 928 | `HTML\08-the-bridge.html` |
| MD | `08-the-bridge` | `0622234511b52509` | 966 | `MD\08-the-bridge.md` |
| HTML | `08-the-lagrangian` | `f3bdf9b050e34ca7` | 1248 | `HTML\08-the-lagrangian.html` |
| HTML | `08-the-verification` | `d996f835fb329b99` | 1421 | `HTML\08-the-verification.html` |
| HTML | `09-the-lagrangian` | `df8cd9438fb9b764` | 1248 | `HTML\09-the-lagrangian.html` |
| HTML | `09-the-lean-survivors` | `8c9eedefd84f7827` | 1712 | `HTML\09-the-lean-survivors.html` |
| HTML | `09-the-ledger` | `093bedddb3578f35` | 2295 | `HTML\09-the-ledger.html` |
| MD | `09-the-ledger` | `5fe5aa498b26a177` | 2311 | `MD\09-the-ledger.md` |
| HTML | `10-the-lean-survivors` | `8e1b1684a3b73595` | 1712 | `HTML\10-the-lean-survivors.html` |
| MD | `10_chapter_10` | `b81aa53ced9c9af7` | 777 | `MD\10_Chapter_10.md` |
| Canon | `11-the-moral-first-chain` | `4c657914686d26c2` | 1530 | `Canon\11-the-moral-first-chain.canonical.md` |
| Canon | `11-the-moral-first-chain` | `489dac3874b4cf7b` | 1544 | `Canon\11-the-moral-first-chain.html` |
| HTML | `11-the-moral-first-chain` | `23bc0ec50a3c1eb8` | 1541 | `HTML\11-the-moral-first-chain.html` |
| Canon | `12-the-is-ought-dissolution` | `54cecd93a070333e` | 1707 | `Canon\12-the-is-ought-dissolution.canonical.md` |
| Canon | `12-the-is-ought-dissolution` | `b3cc4335610fdc3a` | 1737 | `Canon\12-the-is-ought-dissolution.html` |
| HTML | `12-the-is-ought-dissolution` | `391de53d793ea430` | 1729 | `HTML\12-the-is-ought-dissolution.html` |
| Canon | `13-be-fruitful-and-multiply` | `642435b5b50bfa0a` | 1900 | `Canon\13-be-fruitful-and-multiply.canonical.md` |
| Canon | `13-be-fruitful-and-multiply` | `7098cdc6497fd1f1` | 1916 | `Canon\13-be-fruitful-and-multiply.html` |
| HTML | `13-be-fruitful-and-multiply` | `96a1821763d53901` | 1913 | `HTML\13-be-fruitful-and-multiply.html` |
| MD | `2026-07-28_codex_online_prompt_lane4_atom_ledger` | `ab90a4f70de68fb5` | 1007 | `MD\2026-07-28_CODEX_ONLINE_PROMPT_LANE4_ATOM_LEDGER.md` |
| MD | `ai_work_order_html_markdown_cleanup_2026-08-01` | `af08c7035eccb26a` | 1295 | `MD\AI_WORK_ORDER_HTML_MARKDOWN_CLEANUP_2026-08-01.md` |
| MD | `an axiomatic method for cross-domain synthesis` | `77651beb81f71c81` | 242 | `MD\An Axiomatic Method for Cross-Domain Synthesis.md` |
| HTML | `audit of the theophysics workbook stack` | `acba65d2502c0642` | 4961 | `HTML\Audit of the Theophysics workbook stack.html` |
| MD | `audit-00-theophysics-workbook-stack` | `acba65d2502c0642` | 4961 | `MD\AUDIT-00-theophysics-workbook-stack.md` |
| MD | `audit-01-truth-fracture-grace-route` | `d435f25bc5f6d3fc` | 2164 | `MD\AUDIT-01-truth-fracture-grace-route.md` |
| MD | `audit-02-crown-ruling` | `477dcbe839a56257` | 3952 | `MD\AUDIT-02-crown-ruling.md` |
| HTML | `axiom-gap-fill-provisional` | `8ea3e1d696abd019` | 1108 | `HTML\axiom-gap-fill-provisional.html` |
| MD | `canon` | `4dac1e4a181132c8` | 893 | `MD\CANON_INDEX.md` |
| Canon | `canonical_batch_disposition_2026-08-03` | `8e09e84ea085eb20` | 589 | `Canon\CANONICAL_BATCH_DISPOSITION_2026-08-03.md` |
| HTML | `canonical_spiritual-terms` | `24d5e63652149794` | 6091 | `HTML\CANONICAL_spiritual-terms.html` |
| Canon | `character-of-god-from-physics` | `e1cbb5de120c30d6` | 2553 | `Canon\character-of-god-from-physics.canonical.md` |
| Canon | `character-of-god-from-physics` | `5f2f95c5157932e8` | 2579 | `Canon\character-of-god-from-physics.html` |
| HTML | `character-of-god-from-physics` | `22eec76c7fe53d63` | 2570 | `HTML\character-of-god-from-physics.html` |
| HTML | `consciousness` | `a33ad1ad29a18580` | 3835 | `HTML\Consciousness.html` |
| MD | `consciousness lean targets` | `11d9ea153e2a8b06` | 355 | `MD\Consciousness Lean Targets.md` |
| MD | `consciousness stack - draft gather` | `e2747bcec9cfb399` | 929 | `MD\Consciousness Stack - Draft Gather.md` |
| Canon | `consciousness-bottom-up` | `3b77fb1ebb8241cc` | 3962 | `Canon\New BLue\consciousness-bottom-up.html` |
| Canon | `consciousness-chain` | `08fde677aae095eb` | 1617 | `Canon\consciousness-chain.canonical.md` |
| Canon | `consciousness-chain` | `6d1104adcee9735d` | 1942 | `Canon\consciousness-chain.html` |
| HTML | `consciousness-chain` | `86eff13c3e5d3604` | 1939 | `HTML\consciousness-chain.html` |
| MD | `consciousness_claim_matrix` | `5d640dc2ccf36b21` | 1095 | `MD\CONSCIOUSNESS_CLAIM_MATRIX.md` |
| MD | `consciousness_lean_targets` | `b906bea12ee2f031` | 438 | `MD\CONSCIOUSNESS_LEAN_TARGETS.md` |
| MD | `consciousness_lean_targets` | `a718031fa43f5396` | 656 | `MD\CONSCIOUSNESS_LEAN_TARGETS_V2.md` |
| MD | `consciousness_next_actions` | `2dfe218a6be5ab14` | 120 | `MD\CONSCIOUSNESS_NEXT_ACTIONS.md` |
| MD | `consciousness_objection_ledger` | `65b69bb612ba0b9d` | 698 | `MD\CONSCIOUSNESS_OBJECTION_LEDGER.md` |
| MD | `consciousness_public_brief` | `0ca72e6561010266` | 618 | `MD\CONSCIOUSNESS_PUBLIC_BRIEF.md` |
| MD | `consciousness_stack` | `d12fbd7420eb470d` | 293 | `MD\CONSCIOUSNESS_STACK_INDEX.md` |
| MD | `consciousness_technical_brief` | `025f9a2972b514d9` | 927 | `MD\CONSCIOUSNESS_TECHNICAL_BRIEF.md` |
| HTML | `dimensional-gate` | `a027e2f0d8d9640e` | 135 | `HTML\dimensional-gate.html` |
| HTML | `family-00-start-here` | `bc0093007929bb14` | 1976 | `HTML\FAMILY-00-start-here.html` |
| MD | `family-00-start-here` | `409dbbcc37b88542` | 2024 | `MD\FAMILY-00-start-here.md` |
| MD | `formal_theology_atlas_schema` | `de7429a8a89121b9` | 6224 | `MD\FORMAL_THEOLOGY_ATLAS_SCHEMA.md` |
| MD | `formal_verification_ledger` | `56e218ce9b5239d3` | 1777 | `MD\Formal_Verification_Ledger_CANONICAL.md` |
| MD | `fp-002-the-watcher` | `b5bdeaa9559a6d8c` | 2434 | `MD\fp-002-the-watcher-canonical.md` |
| HTML | `god-in-the-equations` | `084eefc02e594d2a` | 1627 | `HTML\god-in-the-equations.html` |
| HTML | `god-in-the-equations-source` | `d803a654f70ad961` | 4799 | `HTML\god-in-the-equations-source.html` |
| HTML | `god-in-the-gaps-through-science` | `64bbcde59f1dbee5` | 2087 | `HTML\god-in-the-gaps-through-science.html` |
| HTML | `god-story-narrative-map-part-1` | `29dbfeef7dc66688` | 2937 | `HTML\god-story-narrative-map-part-1.html` |
| HTML | `god-story-narrative-map-part-2` | `626e6ebf187e57c5` | 9286 | `HTML\god-story-narrative-map-part-2.html` |
| MD | `god_label_index_2026-08-01` | `c5054ee13560733c` | 6558 | `MD\GOD_LABEL_INDEX_2026-08-01.md` |
| MD | `god_title_label_index_2026-08-01` | `b93e56ea0ba33a73` | 1469 | `MD\GOD_TITLE_LABEL_INDEX_2026-08-01.md` |
| HTML | `grace-modes` | `452afd863c360694` | 1241 | `HTML\grace-modes-8efc21c7.html` |
| HTML | `grace-modes` | `452afd863c360694` | 1241 | `HTML\grace-modes.html` |
| MD | `gradient_spec_canonical_ruled` | `ef929e8bc0201ab5` | 1905 | `MD\GRADIENT_SPEC_CANONICAL_RULED.md` |
| HTML | `holding-god-accountable` | `1b74ed95119eb723` | 4177 | `HTML\holding-god-accountable.html` |
| HTML | `how-claims-live-and-die` | `92a24028da2d7714` | 2149 | `HTML\how-claims-live-and-die.html` |
| HTML | `html` | `c5642e401660c8ef` | 44 | `HTML\index.html` |
| HTML | `index.backup-20260728-before-blue-series` | `d8ff9daec1f69854` | 710 | `HTML\index.backup-20260728-before-blue-series.html` |
| MD | `kimi_canon_warmup_and_integration` | `f5983a97959cc056` | 908 | `MD\KIMI_CANON_WARMUP_AND_INTEGRATION.md` |
| MD | `kimi_handoff_consciousness_stack_repeatable_system` | `89914197c7573b89` | 1235 | `MD\KIMI_HANDOFF_consciousness_stack_repeatable_system.md` |
| MD | `kimi_start_here_readme` | `2c79d7b4a05aa742` | 55 | `MD\KIMI_START_HERE_README.md` |
| MD | `kimmy_handoff_shadow_and_plan_a_cost` | `ad4372aa45ba7cce` | 532 | `MD\KIMMY_HANDOFF_shadow_and_plan_a_cost.md` |
| HTML | `l3 consciousness` | `deb33ba57175f4ee` | 5863 | `HTML\l3 consciousness.HTML` |
| MD | `lane4-ontological-layer-axiom-map` | `bcf97b0ff8b13794` | 910 | `MD\LANE4-ontological-layer-axiom-map.md` |
| HTML | `law-1` | `6240bec5194550ac` | 1546 | `HTML\law-1-canonical.html` |
| MD | `layered necessity - derivation grammar` | `2afbc370df66926a` | 318 | `MD\Layered Necessity - Derivation Grammar.md` |
| MD | `layered_necessity_derivation_grammar` | `48a70ab12f5480f6` | 772 | `MD\LAYERED_NECESSITY_DERIVATION_GRAMMAR.md` |
| MD | `lean4_gold_ticket_standard` | `90e877895edc7e42` | 399 | `MD\LEAN4_GOLD_TICKET_STANDARD.md` |
| MD | `lean_clean_slate_reproof_queue_2026-08-01` | `4910067af98c6aa9` | 1627 | `MD\LEAN_CLEAN_SLATE_REPROOF_QUEUE_2026-08-01.md` |
| MD | `lean_current_objects_for_review_2026-08-01` | `0e417d12e91d2b4c` | 880 | `MD\LEAN_CURRENT_OBJECTS_FOR_REVIEW_2026-08-01.md` |
| MD | `lean_full_time_operating_note_2026-08-01` | `5e4c5f79412969d4` | 801 | `MD\LEAN_FULL_TIME_OPERATING_NOTE_2026-08-01.md` |
| MD | `lean_review_packet_credibility_fix_2026-08-01` | `be02fa948fe12370` | 928 | `MD\LEAN_REVIEW_PACKET_CREDIBILITY_FIX_2026-08-01.md` |
| MD | `lean_theorem_family_reduction_2026-08-01` | `ed11c992cc6a47fb` | 750 | `MD\LEAN_THEOREM_FAMILY_REDUCTION_2026-08-01.md` |
| MD | `master equation derivation - status and location` | `b0c86678cabe83d5` | 855 | `MD\Master Equation Derivation - Status and Location.md` |
| HTML | `master-equation` | `6411fd4a9b86a087` | 4876 | `HTML\master-equation-canonical.html` |
| HTML | `master-equation-canonical-with-free-will` | `bf2bc29aefe087b5` | 5135 | `HTML\master-equation-canonical-with-free-will.html` |
| HTML | `master-equation-complete-derivation-chain_v3.1_source_of_truth` | `bf75bc0805603b10` | 21883 | `HTML\Master-Equation-Complete-Derivation-Chain_v3.1_SOURCE_OF_TRUTH.html` |
| HTML | `master-equation-complete-derivation-chain_v3_source_of_truth` | `53ad8a1052091ef5` | 21339 | `HTML\Master-Equation-Complete-Derivation-Chain_v3_SOURCE_OF_TRUTH.html` |
| HTML | `master_derivation_atlas` | `452afd863c360694` | 1241 | `HTML\MASTER_DERIVATION_ATLAS.html` |
| MD | `master_equation_ten_laws_canonical_v4_pending_2026-08-01` | `f90a72f155af0f9b` | 14372 | `MD\MASTER_EQUATION_TEN_LAWS_CANONICAL_v4_PENDING_2026-08-01.md` |
| MD | `master_equation_v4_lean_build_receipt_2026-08-01` | `30f43aadd0433b04` | 477 | `MD\MASTER_EQUATION_V4_LEAN_BUILD_RECEIPT_2026-08-01.md` |
| MD | `master_equation_v4_lean_extraction_note_2026-08-01` | `7bf44696a6a01115` | 1095 | `MD\MASTER_EQUATION_v4_LEAN_EXTRACTION_NOTE_2026-08-01.md` |
| MD | `method-00-from-axiom-to-coherence` | `7322c84de28477d0` | 2316 | `MD\METHOD-00-from-axiom-to-coherence.md` |
| MD | `objection_ledger` | `8c6224900637e4e8` | 246 | `MD\OBJECTION_LEDGER.md` |
| MD | `p-00-opening-postulates` | `23b3493c9c802016` | 1299 | `MD\P-00-opening-postulates.md` |
| MD | `p-01-playground-protocol` | `49b348891f0185e4` | 2036 | `MD\P-01-playground-protocol.md` |
| MD | `p00_openingpostulates_report` | `3970dae9d52f0702` | 212 | `MD\P00_OpeningPostulates_REPORT.md` |
| MD | `paper_structure_template` | `7e93e9b9c3438d1b` | 173 | `MD\PAPER_STRUCTURE_TEMPLATE.md` |
| HTML | `part-zero-finitude` | `5d52cd68cac25938` | 2297 | `HTML\part-zero-finitude.html` |
| MD | `physicist_objection_closure_map` | `62928ef04794fb31` | 1596 | `MD\PHYSICIST_OBJECTION_CLOSURE_MAP.md` |
| MD | `readme` | `cd267dc3dbf9f081` | 124 | `MD\README.md` |
| Canon | `review_first` | `4d092d66fcff596a` | 430 | `Canon\REVIEW_FIRST.html` |
| HTML | `review_first` | `d35cd07e9807323a` | 208 | `HTML\REVIEW_FIRST-319d177f.html` |
| HTML | `review_first` | `d35cd07e9807323a` | 208 | `HTML\REVIEW_FIRST.html` |
| MD | `review_import_report` | `fa0994fff08c0b45` | 453 | `MD\REVIEW_IMPORT_REPORT.md` |
| HTML | `sci-00-the-science-argument-for-triadic-structure` | `69244acf56c62c3a` | 4907 | `HTML\SCI-00-the-science-argument-for-triadic-structure.html` |
| MD | `sci-00-the-science-argument-for-triadic-structure` | `7b16d447c8f7538c` | 4791 | `MD\SCI-00-the-science-argument-for-triadic-structure.md` |
| HTML | `series-opener-template` | `3a9e601d8aa08d4d` | 271 | `HTML\series-opener-template.html` |
| MD | `session_compression` | `dd6b4503b5c9283c` | 2174 | `MD\SESSION_COMPRESSION_20260731.md` |
| MD | `session_compression_20260731_relational_ontology` | `20b3a1977d4e46b7` | 951 | `MD\SESSION_COMPRESSION_20260731_RELATIONAL_ONTOLOGY.md` |
| HTML | `sheet g derivation` | `deb33ba57175f4ee` | 5863 | `HTML\Sheet g derivation.HTML` |
| HTML | `sheet_l3_consciousness` | `a33ad1ad29a18580` | 3835 | `HTML\Sheet_L3_Consciousness.html` |
| HTML | `sheet_l3_consciousness_1` | `a33ad1ad29a18580` | 3835 | `HTML\Sheet_L3_Consciousness_1.html` |
| HTML | `sheet_l3_consciousness_2` | `deb33ba57175f4ee` | 5863 | `HTML\Sheet_L3_Consciousness_2.html` |
| Canon | `source_manifest` | `1564f8b7bc5c1912` | 165 | `Canon\_source_intake\Consciousness_Packet_20260814\SOURCE_MANIFEST.md` |
| HTML | `spiritual-terms` | `8fa57d70b23dc998` | 3590 | `HTML\spiritual-terms-e8047e43.html` |
| HTML | `spiritual-terms` | `f901871218c1f745` | 865 | `HTML\spiritual-terms.html` |
| HTML | `spiritual-terms.backup-20260726-pre-codex-fill` | `c9a78cc07006c4a9` | 1847 | `HTML\spiritual-terms.backup-20260726-pre-codex-fill.html` |
| HTML | `spiritual-termsv2.backup-20260726-pre-codex-fill` | `9265a5be510b978b` | 2060 | `HTML\spiritual-termsv2.backup-20260726-pre-codex-fill.html` |
| MD | `spiritual_terms_atlas` | `af0e4e8b5c8afc58` | 2028 | `MD\Spiritual_Terms_Atlas_CANONICAL.md` |
| MD | `t-00-truth-compendium` | `cf8f96a6a1b928dc` | 3015 | `MD\T-00-truth-compendium.md` |
| MD | `t-00-truth-compendium-codex-pass` | `e409cfc3b7b62b11` | 2760 | `MD\T-00-truth-compendium-codex-pass.md` |
| MD | `t-00-truth-compendium-kimmy-original` | `5f22bb3133cc0484` | 2367 | `MD\T-00-truth-compendium-kimmy-original.md` |
| MD | `t-01-the-hard-questions` | `e3848c43411b1145` | 2638 | `MD\T-01-the-hard-questions.md` |
| MD | `t-01-the-hard-questions2` | `d85e4a22ebe6df99` | 2554 | `MD\T-01-the-hard-questions2.md` |
| HTML | `t-02-the-trinity` | `cd5f011ab1901e9b` | 5412 | `HTML\T-02-the-trinity-canonical.html` |
| MD | `t-02-the-trinity-unified` | `ce7a8f738eda5d2a` | 5004 | `MD\T-02-the-trinity-unified.md` |
| MD | `t-02-the-trinity-unified-codex-review` | `e840af7b0b917686` | 466 | `MD\T-02-the-trinity-unified-codex-review.md` |
| MD | `t-03-the-shadow-before-creation` | `03467cf167d80024` | 1987 | `MD\T-03-the-shadow-before-creation.md` |
| MD | `t01_hardquestions_posture_report` | `bfa19f7e5ab8a5dd` | 353 | `MD\T01_HardQuestions_Posture_REPORT.md` |
| HTML | `templeton-claims-verification` | `d5f8ca9a08b3ec46` | 721 | `HTML\templeton-claims-verification.html` |
| MD | `ten_laws_mapping_tournament_protocol_2026-08-01` | `517b93aa5f69a3b2` | 787 | `MD\TEN_LAWS_MAPPING_TOURNAMENT_PROTOCOL_2026-08-01.md` |
| MD | `the playground protocol` | `7a761f7efd4d130f` | 339 | `MD\The Playground Protocol.md` |
| HTML | `the-7q-universal-classifier` | `d8044bb243ed7bf2` | 1975 | `HTML\The-7Q-Universal-Classifier.html` |
| Canon | `the-christian-walk` | `b332866fbc395ee7` | 10105 | `Canon\the-christian-walk.html` |
| Canon | `the-christian-walk_1` | `528e97799eb01a69` | 10085 | `Canon\the-christian-walk_1.canonical.md` |
| HTML | `the-descent` | `8c90c2a97feba133` | 1309 | `HTML\the-descent-41416f4e.html` |
| HTML | `the-descent` | `d75bb5580b4657b8` | 327 | `HTML\the-descent.html` |
| HTML | `the-math` | `4189ea2307c91ae2` | 1378 | `HTML\the-math.html` |
| HTML | `the-plus-sign` | `fd04cf8fb40ad038` | 1530 | `HTML\the-plus-sign.html` |
| HTML | `the-story-with-receipts` | `ef569398cac9b306` | 61 | `HTML\the-story-with-receipts.html` |
| HTML | `the-ten-laws-story-derivation-portrait` | `6b6d658f5c4e4faa` | 4873 | `HTML\The-Ten-Laws-Story-Derivation-Portrait.html` |
| HTML | `the-ten-laws-story-derivation-portrait.backup-20260710-pre-deep-research` | `4c6c4db81806fb04` | 3673 | `HTML\The-Ten-Laws-Story-Derivation-Portrait.backup-20260710-pre-deep-research.html` |
| HTML | `theophysics-master-map` | `eafb79e6411f5a1f` | 1874 | `HTML\theophysics-master-map.html` |
| MD | `theophysics_corpus_manifest` | `277993487978f477` | 1870 | `MD\THEOPHYSICS_CORPUS_MANIFEST.md` |
| MD | `tp-00-theophysics-blue-sheet` | `394d48c27c6326e9` | 795 | `MD\TP-00-theophysics-blue-sheet.md` |
| MD | `triadic_termination_condensation` | `c08354f2fe9db1f5` | 4274 | `MD\TRIADIC_TERMINATION_CONDENSATION_v2.md` |
| MD | `trinity_and_truth` | `8db8bd9178bc4690` | 4936 | `MD\Trinity_and_Truth_CANONICAL.md` |
| HTML | `unified_derivation_grammar_v0.1` | `349d59a2869a8f5f` | 3204 | `HTML\Unified_Derivation_Grammar_v0.1.html` |
| MD | `unified_derivation_grammar_v0.1` | `d0194cd3e8cac701` | 2167 | `MD\Unified_Derivation_Grammar_v0.1.md` |
| HTML | `unified_derivation_grammar_v0.2` | `d502840a62788fea` | 2534 | `HTML\Unified_Derivation_Grammar_v0.2.html` |
| MD | `unified_derivation_grammar_v0.2` | `10d850d6f1f2079a` | 2267 | `MD\Unified_Derivation_Grammar_v0.2.md` |
| Canon | `w0.1-start-here` | `68c1defb77d83cfb` | 1955 | `Canon\W0.1-start-here.canonical.md` |
| Canon | `w0.1-start-here` | `ce485122e97b514d` | 1977 | `Canon\W0.1-start-here.html` |
| Canon | `w0.2-god-in-the-equations` | `bcb06880079d9e3a` | 2167 | `Canon\W0.2-god-in-the-equations.canonical.md` |
| Canon | `w0.2-god-in-the-equations` | `2be928e9b970fcca` | 2181 | `Canon\W0.2-god-in-the-equations.html` |
| Canon | `w1.1-you-are-god` | `1103501b4b83cb4d` | 3701 | `Canon\W1.1-you-are-god.canonical.md` |
| Canon | `w1.1-you-are-god` | `2b652661d03c0b32` | 3711 | `Canon\W1.1-you-are-god.html` |
| Canon | `w1.2-why-god-built-physics` | `bd888996755e3210` | 3715 | `Canon\W1.2-why-god-built-physics.canonical.md` |
| Canon | `w1.2-why-god-built-physics` | `be277a822a0d565f` | 3724 | `Canon\W1.2-why-god-built-physics.html` |
| Canon | `w1.3-the-plus-sign` | `535fb2618d1927eb` | 1555 | `Canon\W1.3-the-plus-sign.canonical.md` |
| Canon | `w1.3-the-plus-sign` | `60a3c92bff8bb372` | 1567 | `Canon\W1.3-the-plus-sign.html` |
| Canon | `w1.4-god-in-the-gaps` | `cb6741287b0c9a80` | 2058 | `Canon\W1.4-god-in-the-gaps.canonical.md` |
| Canon | `w1.4-god-in-the-gaps` | `6342c4491f95569c` | 2072 | `Canon\W1.4-god-in-the-gaps.html` |
| Canon | `w2.1-part-zero` | `7aae0bc0808114e8` | 2513 | `Canon\W2.1-part-zero.canonical.md` |
| Canon | `w2.1-part-zero` | `30254ca1cabad7bf` | 2560 | `Canon\W2.1-part-zero.html` |
| Canon | `w2.2-single-expression` | `647435d7b5a77eb4` | 1200 | `Canon\W2.2-single-expression.canonical.md` |
| Canon | `w2.2-single-expression` | `5d08604afb00518d` | 1233 | `Canon\W2.2-single-expression.html` |
| Canon | `w2.3-four-axioms` | `af905d1bfdbe1b0a` | 1068 | `Canon\W2.3-four-axioms.canonical.md` |
| Canon | `w2.3-four-axioms` | `f3d4836eb87cbe9a` | 1078 | `Canon\W2.3-four-axioms.html` |
| Canon | `w2.4-finitude` | `33b956efc6d7ba92` | 2353 | `Canon\W2.4-finitude.canonical.md` |
| Canon | `w2.4-finitude` | `f91ed9c97d59cb67` | 2371 | `Canon\W2.4-finitude.html` |
| Canon | `w2.5-why-not-otherwise` | `c42d943c2a59500e` | 1237 | `Canon\W2.5-why-not-otherwise.canonical.md` |
| Canon | `w2.5-why-not-otherwise` | `a8a2bd711ba494b3` | 1211 | `Canon\W2.5-why-not-otherwise.html` |
| Canon | `w2.6-the-descent` | `836a261f99a149cd` | 1299 | `Canon\W2.6-the-descent.canonical.md` |
| Canon | `w2.6-the-descent` | `6cc7159cee796fc9` | 1334 | `Canon\W2.6-the-descent.html` |
| Canon | `w2.7-the-bridge` | `6c9132928732ab59` | 1038 | `Canon\W2.7-the-bridge.canonical.md` |
| Canon | `w2.7-the-bridge` | `8452b94fed6835fd` | 1096 | `Canon\W2.7-the-bridge.html` |
| Canon | `w3-master-equation` | `4552a467ffc5bc27` | 5164 | `Canon\W3-master-equation.canonical.md` |
| Canon | `w3-master-equation` | `df4493dd5a8b9c01` | 5249 | `Canon\W3-master-equation.html` |
| Canon | `w3.3-the-math` | `ee2b705d2c4b42b3` | 1707 | `Canon\W3.3-the-math.canonical.md` |
| Canon | `w3.3-the-math` | `7350e6f28dcb0a2d` | 1881 | `Canon\W3.3-the-math.html` |
| Canon | `w3.4-portrait` | `54376fb151e7ee31` | 4986 | `Canon\W3.4-portrait.canonical.md` |
| Canon | `w3.4-portrait` | `57d6c52a109e0bdf` | 5008 | `Canon\W3.4-portrait.html` |
| Canon | `w3.5-law-1` | `c9929be24b2a520c` | 1580 | `Canon\W3.5-law-1-canonical.canonical.md` |
| Canon | `w3.5-law-1` | `0ac9e6965b71da0b` | 1602 | `Canon\W3.5-law-1-canonical.html` |
| Canon | `w4-trinity-t02` | `31b113e72d9129ae` | 5692 | `Canon\W4-trinity-t02.canonical.md` |
| Canon | `w4-trinity-t02` | `2f77a801e31f001d` | 6120 | `Canon\W4-trinity-t02.html` |
| Canon | `w5-consciousness-mirror` | `cbeb2795f27ba342` | 6182 | `Canon\W5-consciousness-mirror.canonical.md` |
| Canon | `w5-consciousness-mirror` | `a986a21e6d53780d` | 6242 | `Canon\W5-consciousness-mirror.html` |
| Canon | `w7-blue-sheet-tp00` | `b462305330c91f74` | 803 | `Canon\W7-blue-sheet-tp00.canonical.md` |
| Canon | `w7-blue-sheet-tp00` | `482f16d4f096cf3b` | 812 | `Canon\W7-blue-sheet-tp00.html` |
| Canon | `w7.1-the-honest-fight` | `aeb01b68f44e42c9` | 1215 | `Canon\W7.1-the-honest-fight.canonical.md` |
| Canon | `w7.1-the-honest-fight` | `5d1fe9c596bdaaa1` | 1244 | `Canon\W7.1-the-honest-fight.html` |
| Canon | `w7.2-the-verification` | `166e6be33832d703` | 1339 | `Canon\W7.2-the-verification.canonical.md` |
| Canon | `w7.2-the-verification` | `a16f5ad7e75d01c3` | 1350 | `Canon\W7.2-the-verification.html` |
| Canon | `w7.3-the-lean-survivors` | `53010c853379ec69` | 1402 | `Canon\W7.3-the-lean-survivors.canonical.md` |
| Canon | `w7.3-the-lean-survivors` | `034a77b88d8725e1` | 1414 | `Canon\W7.3-the-lean-survivors.html` |
| Canon | `w7.4-the-lagrangian` | `dfbb7b339a655773` | 1046 | `Canon\W7.4-the-lagrangian.canonical.md` |
| Canon | `w7.4-the-lagrangian` | `8e5dbb6e99561863` | 1063 | `Canon\W7.4-the-lagrangian.html` |
| Canon | `w7.5-the-ledger` | `0b6d8a146b8fdc46` | 2230 | `Canon\W7.5-the-ledger.canonical.md` |
| Canon | `w7.5-the-ledger` | `4635b35a42e22fc2` | 2243 | `Canon\W7.5-the-ledger.html` |
| Canon | `w7.6-how-claims-live-and-die` | `b5d69d18d051ee33` | 2027 | `Canon\W7.6-how-claims-live-and-die.canonical.md` |
| Canon | `w7.6-how-claims-live-and-die` | `96f44f53cac42ffe` | 2041 | `Canon\W7.6-how-claims-live-and-die.html` |
| Canon | `w7.8-the-7q-universal-classifier` | `f84580fe4b304762` | 1657 | `Canon\W7.8-the-7q-universal-classifier.canonical.md` |
| Canon | `w7.8-the-7q-universal-classifier` | `2584c040245c6e19` | 1701 | `Canon\W7.8-the-7q-universal-classifier.html` |
| Canon | `w7.9-science-argument-triadic-structure` | `1899f0bef1f11b5e` | 1970 | `Canon\W7.9-science-argument-triadic-structure.canonical.md` |
| Canon | `w7.9-science-argument-triadic-structure` | `90df3401bea3b415` | 2086 | `Canon\W7.9-science-argument-triadic-structure.html` |
| Canon | `w8.1-what-if-we-measured-the-wrong-thing` | `84efc93c27a2c265` | 1200 | `Canon\W8.1-what-if-we-measured-the-wrong-thing.canonical.md` |
| Canon | `w8.1-what-if-we-measured-the-wrong-thing` | `28fed130b8817848` | 1216 | `Canon\W8.1-what-if-we-measured-the-wrong-thing.html` |
| Canon | `w8.2-templeton-dossier` | `e91969b133d98baf` | 717 | `Canon\W8.2-templeton-dossier.canonical.md` |
| Canon | `w8.2-templeton-dossier` | `3a0f936728db57d7` | 760 | `Canon\W8.2-templeton-dossier.html` |
| Canon | `w8.3-axiom-gap-fill` | `418bd35283c5a482` | 926 | `Canon\W8.3-axiom-gap-fill.canonical.md` |
| Canon | `w8.3-axiom-gap-fill` | `13f581d859b47969` | 949 | `Canon\W8.3-axiom-gap-fill.html` |
| Canon | `w8.4-derivation-grammar` | `0ddc9730a8e28607` | 1365 | `Canon\W8.4-derivation-grammar.canonical.md` |
| Canon | `w8.4-derivation-grammar` | `01f73d3405ecf29f` | 1383 | `Canon\W8.4-derivation-grammar.html` |
| MD | `watcher_trinity_actualization` | `35ac5413691bef49` | 3682 | `MD\Watcher_Trinity_Actualization_CANONICAL.md` |
| HTML | `what-if-we-measured-the-wrong-thing` | `579ea7ed58ba5621` | 2718 | `HTML\what-if-we-measured-the-wrong-thing.html` |
| MD | `what_i_found_family_document` | `5167724037dfec71` | 7906 | `MD\What_I_Found_Family_Document.md` |
| MD | `why god made physics - draft module` | `9fe7851ff025477b` | 1264 | `MD\Why God Made Physics - Draft Module.md` |
| HTML | `why-god-built-physics` | `18ec1ce4a6c547f5` | 3578 | `HTML\why-god-built-physics.html` |
| HTML | `why-not-otherwise` | `aa1bd17f808b31f1` | 973 | `HTML\why-not-otherwise.html` |