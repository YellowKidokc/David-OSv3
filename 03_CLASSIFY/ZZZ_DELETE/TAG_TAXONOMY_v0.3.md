# TAG TAXONOMY v0.3 — The Definitive List
**POF 2828 | 2026-09-14 | canonical copy: 999_TEMPLATES/API_LAYER_v0.3**
*This is the instruction book. Every tag in the vault. Closed vocabulary.
If a tag isn't on this list, it doesn't get used — it gets mapped to one that is.
Prefix + descriptor. One facet per tag. No sentence-tags. No duplicates.*

<!-- @template layer=taxonomy version=0.3 -->

---

## THE RULES

1. **Prefix determines facet.** `wf-` = workflow. `ep-` = epistemic. `ct-` = content type. `rc-` = reader category. No prefix = subject tag.
2. **One tag, one meaning.** No aliases. No camelCase variants. Kebab-case only.
3. **Subject tags use domain prefix.** `phys-`, `theo-`, `phil-`, `math-`, `info-`, `cog-`, `soc-`, `meth-`, `cs-`, `tp-` (theophysics integrative).
4. **Maximum depth: prefix-word-word.** Three segments max. `wf-canon-mapping` yes. `wf-canonical-folder-structure-reorganization` no.
5. **Sentence-tags are claims, not tags.** Migrate to claim-atom notes. Tag the note instead.
6. **If you can't pick one, the tag is too broad.** Split it or you picked the wrong facet.

---

## FACET 1: CONTENT TYPE (`ct-`) — what the document IS

*Replaces the old 25-tag list. Down to 10.*

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `ct-argument` | Makes and defends a claim | argument-index, premises, objections, net-assessment |
| `ct-narrative` | Tells the story | narrative-map, interlude, part-i, part-ii |
| `ct-overview` | Survey of a topic or series | overview, introduction, summary, series-results |
| `ct-equation` | Math-primary document | equation-index, math-summary |
| `ct-method` | How we do things | method, user-guide, reading-order |
| `ct-reference` | Lookup material | reference, title-index |
| `ct-implications` | What follows from established claims | implications, insights, recommendations |
| `ct-status` | Progress and project state | status-report, project-progress |
| `ct-outline` | Structural skeleton | outline |
| `ct-source` | Original/external source material | (new — for ingested sources) |

---

## FACET 2: READER CATEGORY (`rc-`) — who it's for

*Was empty. Now populated.*

| Tag | Meaning |
|---|---|
| `rc-general` | Anyone, no prerequisites |
| `rc-curious` | Interested non-specialist |
| `rc-student` | Undergrad-level background |
| `rc-technical` | Graduate/professional level |
| `rc-specialist` | Domain expert |
| `rc-internal` | Framework contributors only |

---

## FACET 3: EPISTEMIC ROLE (`ep-`) — what status its claims have

*Replaces old 23-tag list. Down to 10.*

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `ep-evidence` | Presents evidence for a claim | evidence, supporting-evidence, historical-validation |
| `ep-prediction` | Makes a testable prediction | predictions, falsifiability, falsification-criteria, testability |
| `ep-audit` | Reviews/grades existing claims | audit, audit-integrity, claim-grading-methodology |
| `ep-adversarial` | Attacks a claim to test it | adversarial-review, thought-experiment |
| `ep-consilience` | Shows convergence across domains | consilience, consilience-testing, cross-domain-consilience |
| `ep-defeated` | Claim tested and failed | defeated |
| `ep-open` | Unresolved question | open-question |
| `ep-rigor` | Methodological rigor analysis | rigor, rigor-framework, replication-crisis-mitigation |
| `ep-uniqueness` | Tests whether the claim is novel | uniqueness, uniqueness-theorem, origination-test |
| `ep-falsifiable` | Marks a claim as falsifiable | falsifiable-theology |

---

## FACET 4: WORKFLOW (`wf-`) — vault operations & tooling

*Replaces old 93-tag disaster. Down to 20. The rule: if it's about how the vault works, not what the framework says, it's `wf-`.*

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `wf-obsidian` | Obsidian config, plugins, dataview | obsidian, obsidian-dataview-plugin, dataview, hook, yaml-frontmatter-tagging |
| `wf-canon` | Canonization process and mapping | canon-mapping, canon-organization, canon-sequence, canonical-cleanup, canonical-organization, canonical-folder-structure, proposed-canon-order, blue-canon-organization |
| `wf-file` | File management, moves, naming | file-management, file-moves, file-organization, fileconsolidation, files, folder, folder-architecture, folder-guide, folder-layout, folder-overview, folder-reorganization, folder-rule, folder-structure |
| `wf-html` | HTML generation and conversion | html, html-generation, converter-contract, god-pages, markdown, markdown-syntax |
| `wf-script` | Scripts, automation, tooling | script-audit, script-consolidation, script-inventory, tool-building, tool-suite, automatic-paper-tagging, automatic-tagging, keyword-pattern-matching |
| `wf-pipeline` | Content pipeline and batch processing | content-pipeline, build-pack, implementation-plan, three-tier-separation |
| `wf-scoring` | Paper scoring and ranking | paper-rankings, paper-scores, paper-scoring, paper-series-evaluation |
| `wf-publish` | Publication readiness and strategy | publication-readiness, publication-readiness-evaluation, publication-roadmap, publication-strategy, release-readiness |
| `wf-index` | Indexes, navigation, knowledge graphs | index, navigation, knowledge-graph, graph-connection |
| `wf-lifecycle` | Status tracking, versioning, lifecycle | lifecycle-management, proposed-status, operating-modes, update-procedure |
| `wf-vault` | Vault structure and maintenance | vault-maintenance, vault-organization, operating-system, setup, skeleton |
| `wf-analysis` | Document analysis protocols | document-analysis-protocol, ckg-analysis, ckg-analysis-system-enhancement, attack-surface-analysis |
| `wf-domain` | Domain definitions and architecture | domain, domain-definition, domain-architecture |
| `wf-contract` | Contracts and specifications | contract, instructions, readme |
| `wf-codex` | Codex operations | codex |
| `wf-corpus` | Corpus-level operations | corpus, documentation-gaps |
| `wf-research` | Research workflow | research-workflow, external-research |
| `wf-task` | Task tracking | task, problem-we-were-solving, fixes |
| `wf-world` | World-building and vision | world-building, v2-vision |
| `wf-guard` | Prevention, vandalism, read-only | prevention-protocol, vandalism, read-only |

---

## FACET 5: SUBJECT — domain-prefixed topic tags

*The actual content. Prefix = domain. No prefix mixing. If a paper touches two domains, it gets two tags.*

### `tp-` THEOPHYSICS (integrative) — the framework itself

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `tp-bridge` | Cross-domain mapping or correspondence | bridges, bridge-nodes, cross-domain-analysis, domain-mapping, physics-theology-mapping, and ALL the mapping variants |
| `tp-coherence` | Coherence as metric or concept | coherence, coherence-capital, coherence-functional, coherence-metric, coherence-penalty, coherence-weighting, framework-coherence |
| `tp-descent` | Descent chain and axiom chain | axiom-chain, descent, descent-invariant, descent-rule, biaxiosum, fcmo |
| `tp-entropy` | Entropy, order, decay in framework context | coherent-vs-entropic, entropic-capture, system-decay, order-vs-degradation-modes |
| `tp-debt` | Four debts, moral cost, obligation | four-debts, fourfold-ontological-debt, cost, cost-of-evil, moral-debt, moral-accountability, external-cost-bearer, external-repair |
| `tp-grammar` | Grammar of reality, structural analysis | grammar-claim, grammar-unification, logos-framework, structure, architecture, relational-logic |
| `tp-laws` | Ten laws framework | ten-laws, ten-laws-framework, ten-laws-mapping, ten-super-factors, meta-law-derivation, law-routing |
| `tp-equation` | Master equation | master-equation, master-equation-derivation, master-equation-framework, anti-lagrangian, chi-field, lowe-coherence-lagrangian, spirit-lagrangian |
| `tp-trinity` | Trinitarian structure in the framework | trinitarian-structure, trinity-framework, trinity-physics, triadic-actualization, triadic-structure, crown |
| `tp-unification` | Unification program and claims | unification, two-classes, class-a-vs-class-b, compression-challenge, integration |
| `tp-watcher` | Watcher/witness role | watcher, witness, science-as-witness |
| `tp-method` | Framework methodology | theophysics-methodology, science-rail, theophysics-construction |
| `tp-root` | God as root, ground of reality | god-as-root, ground-of-reality, root-layer, domain-roots |
| `tp-logos` | Logos-specific | logos, logos-papers |

### `theo-` THEOLOGY

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `theo-anthropology` | Theological anthropology, image of God | theological-anthropology, image-of-god, autonomy-trajectory, human-autonomy, the-fall-as-damaged-receiver |
| `theo-christ` | Christology, incarnation, typology | christology, christ-as-pattern, incarnation, i-am-sayings, typology, creation-to-christ |
| `theo-creation` | Creation theology | creation-theology, creation-narrative, creation-as-ordered-gift, ordered-gift |
| `theo-eschatology` | Last things, new creation | eschatology |
| `theo-evil` | Hamartiology, theodicy, nature of evil | theodicy, evil, nature-of-evil, parasitic-evil, counterfeit, sin-is-borrowed-life-turned-against-its-source |
| `theo-source` | Source orientation, revelation | source, revelation, divine-revelation, divine-self-disclosure, scripture, biblical-theology, general-revelation |
| `theo-spirit` | Pneumatology, fruits, sanctification | pneumatology, fruit-of-the-spirit, sanctification, spiritual-discernment, spirituality |
| `theo-salvation` | Soteriology, atonement, redemption | soteriology, atonement, gospel, grace, justice-mercy, redemption, resurrection, salvation-history |
| `theo-method` | Theological method and axioms | axiomatic-theology, theological-axioms, theological-honesty, faith-method |
| `theo-ontology` | Divine attributes, God's nature | divine-attributes, god-s-self-existence, love, divine-solidarity |
| `theo-trinity` | Trinity (theological, not framework-structural) | trinity, trinitarian-ontology, trinitarian-theology, aseity-persons-perichoresis-love |
| `theo-worldview` | Worldview analysis | worldview-analysis, worldview-debt-analysis, worldviews, culture-war |

### `phil-` PHILOSOPHY

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `phil-freedom` | Free will, agency, autonomy | free-will, free-will-constraint, freedom |
| `phil-metaphysics` | Metaphysics, ontology, reality | metaphysics, ontology, reality, identity, relation, dual-aspect-monism |
| `phil-moral` | Moral ontology, is-ought, value | moral-realism, is-ought-gap, morality, value-realism |
| `phil-truth` | Truth, epistemology, knowledge | truth, epistemology, truth-ontology, nature-of-truth, epistemic-method, foundations-of-science, truth-as-precondition-for-argument |
| `phil-mind` | Philosophy of mind | (absorbs philosophy-of-mind) |
| `phil-religion` | Philosophy of religion | (absorbs philosophy-of-religion) |
| `phil-science` | Philosophy of science | (absorbs philosophy-of-science, philosophy-of-physics) |

### `math-` MATHEMATICS & FORMAL SYSTEMS

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `math-algebra` | Algebra, equations | algebra, algebraic-resolution, equations, mathematical-truth |
| `math-axiom` | Axiomatics, logic, formal foundations | axiom, axiom-evaluation, formal-logic, mathematical-logic |
| `math-lean` | Lean 4 formal verification | lean4, formalization, formal-verification |
| `math-model` | Mathematical modeling, dynamical systems | mathematical-modeling, dynamical-systems, algebraic-modeling |
| `math-geometry` | Differential geometry, variational calculus | differential-geometry, variational-calculus |

### `phys-` PHYSICS

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `phys-cosmology` | Cosmology, big bang, Hubble tension | cosmology, big-bang, hubble-tension, hubble-tension-prediction, cosmological-origin |
| `phys-field` | Field theory, Lagrangian, gauge theory | lagrangian, lagrangian-formalism, field-theory, gauge-theory, interaction-lagrangian, matter-fields |
| `phys-quantum` | Quantum foundations, measurement | quantum-foundations, quantum-mechanics, measurement-problem, quantum-collapse, von-neumann-chain |
| `phys-thermo` | Thermodynamics, entropy | thermodynamics, entropy, entropy-penalty, second-law-necessity |
| `phys-unification` | Physics unification, emergence | emergence-of-physics, something-from-nothing, agency-in-physics, unified-field-theory |
| `phys-observer` | Observer theory, measurement | observer-theory, observer-coupling, observer-transparency, participatory-universe |

### `info-` INFORMATION & SYSTEMS THEORY

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `info-theory` | Information theory | information-theory, algorithmic-information-theory |
| `info-systems` | Systems theory, systems thinking | systems, systems-theory, systems-thinking, systems-design |
| `info-entropy` | Entropy in information context | entropy-modeling, measurement-theory |

### `cog-` COGNITIVE & NEURO

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `cog-consciousness` | Consciousness studies | consciousness, consciousness-as-witness, consciousness-role, first-person-presence, interiority |
| `cog-neuro` | Neuroscience, dishbrain | dishbrain, neuroscience |
| `cog-info` | Information-theoretic consciousness | information-theoretic-consciousness |

### `soc-` SOCIAL SCIENCES

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `soc-history` | Historical analysis, data, trends | history, historical-analysis, historical-data, historical-trends |
| `soc-institution` | Institutional analysis, drift, capture | institutional-analysis, institutional-capture, institutional-drift, institutional-dependency |
| `soc-economics` | Economics | economics, social-economics |

### `meth-` METHODOLOGY & PRACTICE

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `meth-assessment` | Quality assessment, scoring | quality-assessment, multi-metric-quality-assessment, research-paper-quality-assessment |
| `meth-calibration` | Calibration, bias correction | calibration, bias-calibration, calibration-shift |
| `meth-claims` | Claim modeling, classification | claim, claim-atom, claim-classification, claim-labeling, knowledge-atom, regime-classification |
| `meth-foundations` | First principles, methodology | first-principles, scientific-methodology, inquiry |
| `meth-research` | Research evaluation and workflow | research-evaluation |

### `cs-` COMPUTER SCIENCE

| Tag | Meaning | Old tags absorbed |
|---|---|---|
| `cs-ai` | Artificial intelligence, ML | artificial-intelligence, machine-learning |
| `cs-data` | Data analysis, provenance | data-analysis, data-provenance |
| `cs-software` | Software engineering, architecture | software-engineering, software-architecture, software-automation |
| `cs-nlp` | Natural language processing | natural-language-processing |

---

## SERIES TAGS (`series-`)

*One tag per named series. Used in frontmatter to group papers for series aggregation.*

| Tag | Series |
|---|---|
| `series-genesis-quantum` | Genesis to Quantum |
| `series-consolidated` | Consolidated Docs (CONSOL_01–21) |
| `series-one-story` | THE ONE STORY |
| `series-master-eq` | Master Equation papers |
| `series-boundary` | Boundary Proof family |
| `series-fruits` | Fruits of the Spirit derivations |
| `series-descent` | Descent chain papers |
<!-- Add as series are identified. Open vocabulary within the series- prefix. -->

---

## TAG COUNT SUMMARY

| Facet | Prefix | Count | Old count |
|---|---|---|---|
| Content type | `ct-` | 10 | 25 |
| Reader category | `rc-` | 6 | 0 |
| Epistemic role | `ep-` | 10 | 23 |
| Workflow | `wf-` | 20 | 93 |
| Theophysics | `tp-` | 14 | 147 |
| Theology | `theo-` | 12 | 110 |
| Philosophy | `phil-` | 7 | 35 |
| Mathematics | `math-` | 5 | 9 |
| Physics | `phys-` | 6 | 33 |
| Information | `info-` | 3 | 2 |
| Cognitive | `cog-` | 3 | 6 |
| Social sciences | `soc-` | 3 | 7 |
| Methodology | `meth-` | 5 | 20 |
| Computer science | `cs-` | 4 | 1 |
| Series | `series-` | 7+ | 0 |
| **TOTAL** | | **~115** | **516** |

**516 → ~115.** 78% reduction. Every surviving tag has one meaning, one prefix, one facet slot.

---

## DOMAIN CONTROLLED VOCABULARY (for YAML `domain:` field)

*These are NOT tags. These are the closed ~10 domain values used in frontmatter.*

| Domain value | Maps to tag prefix |
|---|---|
| `Theophysics` | `tp-` |
| `Theology` | `theo-` |
| `Philosophy` | `phil-` |
| `Mathematics` | `math-` |
| `Physics` | `phys-` |
| `Information Theory` | `info-` |
| `Cognitive Science` | `cog-` |
| `Social Sciences` | `soc-` |
| `Methodology` | `meth-` |
| `Computer Science` | `cs-` |

---

## MIGRATION RULES

1. Any tag not on this list gets mapped to its absorbing tag above.
2. Sentence-tags (`a-readable-world-makes-deeper-sense-if-reality-is-rooted-in-a-speaking-god`) become claim-atom notes. Tag the note `tp-logos` or whatever fits.
3. CamelCase and underscore variants die. `InterdisciplinaryResearch` → `meth-research`. `Systems_Theory` → `info-systems`.
4. Duplicate aliases resolved per the merge table in the old taxonomy. The canonical form is the one on this list.
5. `systems` (56 papers) splits: framework-structural uses → `tp-grammar`, information-theoretic uses → `info-systems`, vault operations → `wf-vault`.
6. `theology` (66 papers) splits: use the specific `theo-` subtag. Bare `theology` no longer exists.
7. `consciousness` (36 papers) splits: `cog-consciousness` for the subject, `tp-watcher` for the framework role.

---

_POF 2828 · not a probability of truth · human ruling required_

<!-- @template layer=taxonomy version=0.3 end -->
