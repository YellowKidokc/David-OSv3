---
title: "SELAH — Canonical Region Marking & Self-Healing Spec"
version: "0.1"
date: "2026-08-18"
status: "DRAFT — awaiting David's ratification of name + tier model"
feeds: "CURSOR_HANDOFF_2026-08-18 (Thing 1 port: classify_canon_standing; Thing 2: SCALE_SCAN_ALL)"
integrates: "canon_gate.py / canon_rules.json (register-compiled rules), FIS scanner, future PocketBase backbone"
tags: [canon, selah, self-healing, fis, specification]
source_copy: "\\\\192.168.2.50\\h_hp\\Desktop\\SELAH_SPEC_v0_1.md"
---

# SELAH SPEC v0.1

> Name: **Selah** — the Psalmic in-text marker: "pause, weigh this; it is load-bearing."
> Function: make canonical passages machine-addressable so machines never touch prose.

---

## 1. THE TWO MARKERS

### 1.1 Sealed block (Tier 1) — the fence

```markdown
%% selah:LAW-4-POTENTIAL v=7 %%
V(r) = −α_s/r + k·r   [Cornell confining form]
%% /selah %%
```

- `selah:<ENTITY-KEY>` — must exist in `canon_registry.json`. No registry entry, no seal.
- `v=N` — version of the canonical content the block carries.
- Content between fences is the ONLY text the healer may ever modify.

### 1.2 Inline sigil (Tier 2) — the reference

```
…as §LAW-4 establishes, the confinement term grows linearly…
```

- `§<ENTITY-KEY>` — zero-width commitment: "I mean the registered object."
- Verify-only: scanner checks the key exists and the sentence's claim matches the
  registered form. Never rewritten.

### 1.3 Unmarked prose (Tier 0)

Everything else. Watched by canon_gate pattern rules (drift flags, legacy IDs).
Flag-only, forever. This is the containment doctrine: **write-permission ends at the fence.**

---

## 2. REGISTRY — canon_registry.json

```json
{
  "LAW-4-POTENTIAL": {
    "version": 7,
    "content": "V(r) = −α_s/r + k·r   [Cornell confining form]",
    "sha256": "…",
    "ruling": "CONSOLIDATED_07 §6 Law 4 + AM-FRUITS-01 §6 (Cornell footnote)",
    "mode": "MAPPED",
    "sealed_required": true
  }
}
```

The registry is the single source of truth. (Phase 1: JSON file beside canon_rules.json.
Phase 2: a PocketBase collection — same schema, multi-machine sync.)

---

## 3. VERSION RULES (the interlock)

| File says | Registry says | Verdict | Action |
|---|---|---|---|
| v=7 | v=8 | SEAL_STALE | Queue update to approval queue |
| v=8 | v=7 | SEAL_AHEAD | **Report. Never downgrade.** A newer doc must not be clobbered by an old scanner |
| v=8, content ≠ registry hash | v=8 | SEAL_TAMPERED | Report — same version, different content = drift inside the seal |
| no seal, content matches registry | — | UNSEALED_CANON | Report as seal candidate (feeds LLM proposal station) |
| unclosed fence | — | SEAL_BROKEN | Flag file, skip entirely — no partial edits, ever |

---

## 4. THE HEALING LOOP (deterministic write path)

```
scanner detects SEAL_STALE
  → approval_queue item (file, key, old v, new v, diff)
  → human (or rule with auto=true) approves
  → single writer swaps fenced content only
  → SHA-256 before/after → canon_ledger.jsonl
  → FIS re-scan updates Canon Standing column
```

Respects Thing 2 discipline: the approval queue serializes writes, so the healer can
never double-write while RUN_SCAN_CHAIN_2.ps1 holds the WAL.

---

## 5. INTELLIGENCE STATIONS (LLM — propose-only)

| Station | Job | Output |
|---|---|---|
| Seal proposal (bootstrap) | Read unmarked canon docs (Cannon folder, 00_CANONICAL, FORM-C ~604-hit backlog); propose fence placements + entity keys | Queue items for human ratification |
| Semantic diff drafting | When a ruling changes a sealed block's meaning (not just version), draft the replacement inside the fence | Queue item with full fenced diff |

The LLM never writes. Version numbers write. Docker placement: Ollama (or Claude
bridge) container beside PocketBase on the NAS; stations read from / write to the
approval queue only.

---

## 6. FIS / STANDING INTEGRATION (Thing 1 port hooks)

- `classify_canon_standing()` reads seal state as its primary signal
- New drift_flags: `SEAL_STALE`, `SEAL_AHEAD`, `SEAL_TAMPERED`, `SEAL_BROKEN`, `UNSEALED_CANON`
- FIS.html Canon Standing column: sealed-current ✅ / sealed-stale ⏳ / unsealed ⚠️ / broken ❌
- `.canon.sidecar.json` gains: `seals: [{key, version, hash, line_start, line_end}]`

---

## 7. FAILURE MODES & GUARDS

- **Seal sprawl** — too many seals = noise. Guard: registry gate; a key requires a
  ruling ID. Target: 50–200 seals corpus-wide, not thousands.
- **Version fork** — two docs both claim v=8 with different content. Guard:
  SEAL_TAMPERED hash check catches it; registry content hash is the arbiter.
- **Fence corruption** — unclosed/mismatched fences. Guard: SEAL_BROKEN skips the file;
  no partial edits under any circumstance.
- **Registry corruption** — the registry is the crown jewel. Guard: git-tracked,
  append-only changelog, David-signs-version-bumps.

---

## 8. PHASES

- **Phase 0 (this week):** ratify name + tiers; hand-write seals for the Ten Laws,
  FORM-C, BC1–BC9, the fruit spine; add `SEAL-VERIFY` rule to canon_rules.json.
- **Phase 1:** canon_gate learns seal verification; FIS Canon Standing column;
  LLM bootstrap pass over Cannon + 00_CANONICAL.
- **Phase 2:** registry → PocketBase collection; approval queue multi-machine;
  Ollama container on NAS for the two stations.
