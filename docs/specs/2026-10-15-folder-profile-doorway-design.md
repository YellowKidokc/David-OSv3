# Folder Profile Doorway + Pre-Flight Gate — Design

Date: 2026-10-15 · Status: implemented 2026-10-15 · Repo: David-OSv3

## 1. Background

The FIS rule layer exists as **data**, imported from the design workbooks into
`config/rules/`: 15 folder profiles (`folder_profiles.28pof.v1.json`), the 20-question
onboarding flow (`onboarding_questions.v1.json`), 16 review gates (`review_gates.28pof.v1.json`),
the scanner pipeline (`scanner_pipeline.v1.json`), the folder marker contract
(`folder_marker_contract.v1.json`), canon rules, symptom registry, severity scale, and a
22-step build order whose step 5 is literally *"Folder registry + policy engine — folders
need profiles, not scripts."*

The FIS **grammar** lives in the master workbook (`FIS_Rule_Automation_Grammar.xlsx`):
`field → operator → value → action + guardrail + approval_mode`, with 63 fields, 35
namespaced operators, 32 actions with destructive levels and default safety modes,
12 guardrails (GR-001..012), a 24-pair compatibility matrix, per-action conditions
(`blocked_if`, required guardrails), and a ledger schema. Its core rules:

- *Nothing executes until preview/approval says it can.*
- *APIs suggest. The registry learns. The scanner scores. The user approves.*

**What was never built:** (a) a doorway that asks the questions and writes folder profiles
(`config/folder_profiles.json` still ships its `/path/to/watch` placeholder), and (b) a single
pre-flight gate that every file action passes through. `engine/capability.py` is a different
gate (category data-access tiers), not an action-rule check.

This spec builds those two pieces.

## 2. Goals / non-goals

**Goals**

1. A wizard (`01_PROFILE`) that runs the 20 onboarding questions against a folder, pre-fills
   answers from scanner evidence + prediction-harness suggestions, and writes the profile.
2. A gate (`engine/gate.py`) that evaluates every proposed file action against the rule
   stack and returns allow / preview / ask / block — where **block and ask always route to
   the user**, who may approve once, approve always-for-this-folder, or reject. The gate is
   never the final authority; the user is.
3. Wire the gate into the action-carrying tools that exist today (rename engine first).
4. Keep everything portable to Rust later (see §8).

**Non-goals (this spec)**

- Automation runtime (workbook AUTO-* rules stay disabled by design).
- Structural similarity engine (STR/SS/DER sheets) — separate project.
- Argument-matrix HTML report generator — separate spec; it runs *inside* these profiles.
- Rewriting existing scanners, symptom detectors, or the ledger.

## 3. Components

### 3.1 Rule-data completion (`config/rules/`)

Import the remaining grammar sheets as versioned JSON, matching existing conventions:

| New file | Source sheet | Contents |
|---|---|---|
| `guardrails.v1.json` | Guardrails | GR-001..012: severity, default_behavior, applies_to |
| `actions_master.v1.json` | Actions_Master | 32 actions: family, destructive_level, requires_preview/approval, default_safety |
| `action_conditions.v1.json` | Action_Conditions | per-action required_preconditions, blocked_if, required_guardrails, approval_default |
| `compatibility_matrix.v1.json` | Compatibility_Matrix | 24 pairs: Yes/No/Required/Conditional/Blocks/Preferred |

ID reconciliation: `SYM-xxx` (workbook) becomes canonical; the imported `S01..S40` keys in
`symptom_registry.28pof.v1.json` get a `canonical_id` mapping field added, files unchanged
otherwise.

### 3.2 Profile store

- Global: `config/folder_profiles.json` — replace placeholder with real profiles; validated
  against `schemas/folder_profiles.schema.json` (exists) via `hub/config/folder_profiles.py`
  (loader/matcher exists).
- Per-folder: `.folder.fmeta` JSON marker, per `folder_marker_contract.v1.json`
  (role, safety policy, profile id, questionnaire version, timestamps). Write policy:
  never inside system folders, do-not-touch roots, dependency/cache/venv folders.
- Missing profile → `default_profile_template` from `onboarding_questions.v1.json`
  (preview-only, delete-never, approval-required moves). Fail closed.
- Profiles also carry **relevance and output shape**, not just safety: `irrelevant_actions`
  (action families never proposed here), `sidecar_writer` (e.g. `obsidian` vs `default`),
  and `report_type` (which FIS HTML flavor this folder gets). Defaults keep current behavior.

### 3.3 `01_PROFILE` wizard (`03_CLASSIFY` sibling: `01_PROFILE/`)

PySide6 GUI (repo standard), plus a headless CLI mode (`--answers file.json`) for scripting.

Flow per folder:
1. Scanner evidence pass (read-only): extensions, markers (`.obsidian`, `.git`, `_API/*.json`,
   transcripts), name patterns → candidate answers.
2. Prediction harness suggests each answer (harness events: subject=folder path,
   facets=question ids); confidence shown per suggestion.
3. User confirms/edits 3–5 **visible** questions (the rest auto-confirmed when confidence
   is high AND the question is low-risk; `do_not_touch`, `important_files`, `sensitive_classes`,
   `public_private_boundary` are always shown).
4. Evidence-based follow-ups fire on scanner triggers (`many_excel_files`,
   `project_root_danger`, …) exactly as defined in `onboarding_questions.v1.json`.
5. Writes: profile entry in `folder_profiles.json`, `.folder.fmeta` marker, harness ledger
   events (accepted/rejected suggestions → engine scoring).

### 3.4 The gate — `engine/gate.py`

Pure stdlib, no I/O except reading rule JSONs at construction. Single entry point:

```
decision = gate.evaluate(action_id, target_paths, context) -> Decision
```

`context`: folder profile (or default), batch size, confidence, trigger (manual/scheduled),
session overrides. `Decision`: `ALLOW | PREVIEW | ASK | BLOCK`, plus `fired_rules` (list of
rule ids + human-readable reasons), plus `required_guardrails`.

Evaluation order (first BLOCK wins; otherwise most restrictive verdict):
0. **Relevance** — a profile can mark whole action families as not-applicable (e.g. a
   `program_root` profile never proposes dedupe/spread; an `obsidian_vault` profile routes
   sidecar writing to the Obsidian-aware writer and selects the vault-flavored FIS.html
   report type). Not-applicable actions are silently dropped from proposals, never asked about.
1. Guardrails GR-001..012 (system folders, secrets, project roots, ledger requirement…)
2. Folder profile `blocked_actions` / `allowed_actions`
3. Action conditions `blocked_if` (e.g. rename blocked on protected/project_root/collision)
4. Review-gate thresholds (bulk >20 rename/move, >50 archive, any delete → ask)
5. Compatibility matrix (when actions are chained)
6. Profile approval floor + action `default_safety` (preview_only / suggest_only /
   approval_required / blocked)

`BLOCK` is reserved for never-negotiables (system folders, secrets). Everything else that
fails becomes `ASK` — surfaced to the user with the fired rules and three choices:
**approve once / always allow in this folder / reject**. Overrides are written to the ledger
(`engine/ledger.py`, workbook Ledger_Schema fields) and fed to the prediction harness as
rulings, so engines learn per-folder approval patterns — and pre-fill, never silently pass.

### 3.5 Wiring (phased)

- **Phase 1:** `03_CLASSIFY/03_RENAMING/rename_engine.py` + `renamer_gui.py` call the gate
  per batch; gate verdict drives the existing review UI (ASK rows shown with fired rules).
- **Phase 2:** FIS scanner marker writes (`write_marker_if_profile_allows`) and
  `engine/rename_planner.py`.
- **Phase 3:** anything that moves/archives (nothing does yet without approval — keep it so).

### 3.6 Prediction tie-in

Harness lives at `03_CLASSIFY/02_CLASSIFICATION/harness`. New adapter
`harness/adapters/gate_events.py`: gate outcomes and user overrides become `Event`s;
per-facet ledgers `data/gate_<facet>.db`. Engines: reuse `frequency_baseline`,
`recency_baseline`, `name_words`, `river_online`; add no new engines in v1.

## 4. Data flow

```
New folder found
   │ (read-only evidence scan)
   ▼
01_PROFILE wizard ── pre-filled by harness ── user confirms
   │ writes folder_profiles.json + .folder.fmeta
   ▼
Action proposed (rename/move/…)
   │ engine/gate.evaluate()
   ├── ALLOW/PREVIEW → existing preview flow
   └── ASK/BLOCK → user dialog: fired rules + approve once / always-here / reject
                    → ledger + harness learns
```

## 5. Error handling

- Missing/corrupt rule JSON → gate fails closed (everything ASK) with a loud startup error.
- Missing profile → default template (preview-only).
- NAS path unreachable → actions on that root become ASK; reads proceed.
- Wizard interrupted → nothing written (write happens once, at confirm).

## 6. Testing

- `tests/test_gate.py`: pure-function tests over fixture rule sets — each GR, each review-gate
  threshold, compatibility Blocks, override recording. Fixture folders in a tmp dir.
- `tests/test_profile_wizard.py`: headless mode — answers file → profile + marker written;
  evidence pre-fill produces expected suggestions on a fixture tree.
- Keep gate I/O-free so the same fixtures can later drive a Rust port (differential testing:
  same input → same decision from both implementations).

## 7. Files touched / created

| Path | Change |
|---|---|
| `config/rules/guardrails.v1.json` etc. (4 files) | new, imported from grammar workbook |
| `config/folder_profiles.json` | real profiles replace placeholder |
| `engine/gate.py` | new |
| `01_PROFILE/` (wizard GUI + CLI + README + bat) | new |
| `03_CLASSIFY/03_RENAMING/rename_engine.py`, `renamer_gui.py` | gate call added |
| `03_CLASSIFY/02_CLASSIFICATION/harness/adapters/gate_events.py` | new |
| `engine/symptoms` / symptom registry | add `canonical_id` SYM mapping (data only) |
| `tests/test_gate.py`, `tests/test_profile_wizard.py` | new |

## 8. Rust portability discipline

The later Rust port is cheap **if** this spec's core obeys three rules:

1. Gate + profile logic are pure functions over JSON-deserializable data (dicts, lists,
   strings, numbers) — no metaclasses, no dynamic imports, no monkey-patching.
2. All rule knowledge lives in `config/rules/*.json` — Rust reads the same files unchanged.
3. Decisions are value objects with a stable JSON shape (this becomes the differential-test
   contract: Python is the reference oracle, Rust must match it on the fixture corpus).

Ports directly: gate, profile store, rule evaluation, ledger schema, marker format.
Does not port (rewrite or keep Python): PySide6 GUI, prediction harness deps (river/sklearn),
LLM plumbing. Precedent: `tools/fis/rust/` already proves the scanner skeleton in Rust.

## 9. Open questions

1. Wizard scope per-run: profile one folder at a time, or walk a root and batch-profile
   (recommended: single folder first, batch later)?
2. Should `always allow in this folder` overrides expire (e.g. re-ask after 90 days)?
   (Workbook is silent; default: no expiry, but listed in FIS.html so you can revoke.)
3. GUI home: new `01_PROFILE/` top-level, matching the numbered-step layout of `03_CLASSIFY`.
