---
title: "V3 SALVAGE MANIFEST — Parts Inventory for David-OSv3"
version: "1.0"
date: "2026-08-18"
status: "READY FOR CURSOR — pairs with CURSOR_HANDOFF_2026-08-18.md"
purpose: "Everything worth stripping from v1/v2/salvage/other repos into David-OSv3, with sources named so nothing gets hunted blind"
tags: [david-os, fis, salvage, canon, sidecar, approval-queue]
source_copy: "\\\\192.168.2.50\\h_hp\\Desktop\\V3_SALVAGE_MANIFEST_v1.md"
---

# V3 SALVAGE MANIFEST

> Rule: the most up-to-date system is v3, but the *parts* live in the others.
> Port parts, not stacks. v3's `fis_sidecar.py` is the standing object of record —
> salvage feeds it, nothing replaces it.

---

## 1. PORT INTO v3 (in dependency order)

| # | Part | Source | Target in v3 | Why | Status 2026-08-18 |
|---|---|---|---|---|---|
| 1 | Sidecar contract schema | `David-OS/docs/schemas/file-sidecar-contract.md` | already in v3 at that path | Canonical "what a sidecar is" | **in tree** |
| 2 | Protected sidecar types + folder policy map | `David-OS/config/rules/sidecar_rules.example.json` | `file-intelligence-system/config/sidecar_rules.json` | .fmeta/.chi/.fisnote/.fistag/.fisdead | **ported** (also keeps example.json) |
| 3 | Canon nomination doctrine | `AI-CREW/CANON_NOMINATION_PROTOCOL.md` | `docs/canon/CANON_NOMINATION_PROTOCOL.md` | One sidecar per file; append-don't-overwrite; no sidecar = no opinion | **not copied yet** — policy already encoded in fis_sidecar (no overwrite of human sidecars) |
| 4 | Deep standing engine | salvage `chi_jm_diagnostic_engine_v4_gold.py` | cheap `classify_canon_standing()` in `fis_sidecar.py` now; deep engine still salvage | canon_ready_score + canonical_identity_assessment | **shallow in v3**; deep port still open |
| 5 | .canon.sidecar.json writer schema | `tools/sidecar_creator.py` | `file-intelligence-system/fis_sidecar.py` | status / rulings / contradictions | **verified** — plus lineage, claim_ids, evidence_tier, wanted, written, boundary, seals[] |
| 6 | Gate consolidation | `000_TOOLS/canon_gate_v2.py` + v3 per-line + `Python-WEB/canonical_gate.py` + new `canon_gate.py` | `engine/canon_gate.py` — ONE gate | Four gates; merge into canon_rules.json | **open** |
| 7 | Promote/audit routing | salvage `tke_4q_router.py` | `engine/router.py` | EXTRACT_CANON → `_canonical_candidates`; `needs_canonguard_audit` | **open** |
| 8 | Ensemble decision feed | toast clicks → `engine/preference/ensemble.py` | `file-intelligence-system/approval-gui/server.py` | Every click teaches all five, then cascade | **wired locally**; falls back to River if ensemble import fails |
| 9 | Claims-sidecar pattern (website) | `FaiththruPhysics/shared/CLAIMS_SPEC.md` | reference only | Approve-then-render for Selah UX | **reference only — do not port code** |

## 2. DO NOT PORT

- `D:\_FIS_ROOT_SIDECAR_ARCHIVE` (86,320 files) — snapshot archive; v3 reads sibling sidecars, never walks this. Keep as cold storage.
- `.fisnote` per-file notes — folder-level only in the default chain; per-file stays opt-in (`--file-notes`).
- Forge `ai_sidecar.py` / tom_fis_api GUI experiments — different stacks; mine ideas, not code.

## 3. UNIVERSAL APPROVAL — the design in one box

```
ALL PRODUCERS (scanner, tagger, namer, canon_gate, selah healer, LLM stations)
   │  write action_proposal{type, target, before, after, score, rule_id}
   ▼
ONE QUEUE (jsonl now; fis_folder_memory.sqlite approval_queue later; PocketBase later)
   ▼
ONE CONSUMER (toast GUI :10778, 500-card paging)
   ▼
every decision → ensemble.learn() (River + Markov + GBDT + VW + frequency)
   ▼
per-action-type trust thresholds → auto-act earned, never assumed
```

`action_proposal` is defined in `docs/architecture/hub-overview.md`. Lossless rename proposals now use `action_proposal.v1` while keeping GUI fields (`id`, `current_name`, `proposed_name`).

- **Auto-propose** at thresholds (standing ≥ 0.75 → lossless) — wired. Low-grade files do not spam the toast.
- **Auto-act** starts at sidecar writes and sealed-block version syncs. Renames/moves stay human (`auto_act: false`) until cascade proves an engine on that action type; then flip per type with ledger entries.

Queue is still `approval-gui/fis_proposals.jsonl`, not yet an `approval_queue` SQLite table.

## 4. SELAH INTERLOCK (from SELAH_SPEC_v0.1)

- Seal verification feeds standing: all-seals-current raises score beyond CHI-only confidence (wired as a +0.12 bump when sidecar `seals[]` are present and not stale/ahead/tampered/broken).
- Drift flags: `SEAL_STALE` / `SEAL_AHEAD` / `SEAL_TAMPERED` / `SEAL_BROKEN` / `UNSEALED_CANON` — first four read from sidecar seal state; `UNSEALED_CANON` still needs registry matching.
- Selah healer is another proposal producer — not implemented until name/sigil/keys are ratified.

## 5. OPEN ITEMS

- [ ] Push local v3 wiring (`fis_sidecar.py`, toast ensemble feed, 500-card) to GitHub — wait for an explicit push ask.
- [x] Verify `fis_sidecar.py` absorbed `sidecar_creator.py` schema (item 5).
- [ ] Merge four gate rule sets into `canon_rules.json` without losing FORM-C and the 604-hit backlog rules.
- [ ] `SCALE_SCAN_ALL.ps1` — sequential writer (desktop → H: → D:/Z:), then `fis_html_index` fill.
- [ ] Page the 500-card GUI properly (cap lifted; not paged).

## 6. TONIGHT — federated search (David, 2026-08-18 23:00)

Not building until David points at the next folder. Shape:

- **Speed:** Desktop scan is `--no-local-ai` (fast lane). The "slow" GUI mode is the daemon crawler (`fis_daemon.py`), not this pass. Remaining slowness is SHA-256 of big Desktop binaries + two writers on one SQLite.
- **Rename HTML later:** selectable rows, editable proposed name, ensemble predictions visible — closer to Master Equation HTML than the current file-block table. Same toast queue (`action_proposal`).
- **Per-drive SQLite:** one `fis_folder_memory.sqlite` (or copy) on each HDD after that drive's scan.
- **Aggregate:** classifications + every `FIS.html` path into a master index (`fis_html_index` + search on 10779).
- **Talker:** one AI that queries all drive SQLites (federated search), not one mega-file. HTML stays the view; SQLite stays the index.
- Skip `H:\Desktop 2`. Desktop one (`H:\Desktop`) is the live HTML/link pass.

