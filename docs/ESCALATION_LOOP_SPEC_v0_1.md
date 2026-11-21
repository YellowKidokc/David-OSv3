---
title: The Escalation Loop — script first, then Jev, then blind pairs, then DeepSeek, then leave it
version: 0.1-draft
date: 2026-11-21
requirements_by: David Lowe
drafted_by: Claude (Opus 5.5)
build_owner: open (Codex suggested)
review_state: draft_for_review
---

# The Escalation Loop

## What it is for

We want every file in Obsidian named, labelled and keyed without anyone hand-checking 77,000 files, and without any AI quietly guessing. The rule is simple: **the cheapest thing that can answer honestly answers. When it can't, it says so with a code, and the question climbs one rung. When nothing can answer, the question waits for David. We never push.**

Nothing on any rung renames, moves or deletes. Every rung only proposes. Rule Brick principles 1–10 apply throughout; David's approval is the only authority (Nov 20 rule).

## The five rungs

```
RUNG 0  Python (106 namer, paper key local parts)   free, exact     -> answer  or  STOP CODE
RUNG 1  Jev                                          cheap           -> answer  or  climb
RUNG 2  Blind pair x up to 3 rounds                  cheap x 2-6     -> answer  or  climb
RUNG 3  DeepSeek with a compact bundle               a few cents     -> answer  or  climb
RUNG 4  UNRESOLVED queue                             David / later   -> stays visible, never forced
```

### Rung 0 — the script runs as far as it can

The script answers everything it can answer exactly and emits a **stop code** for everything it can't. One closed list of codes, shared by every script, so the loop knows what kind of question each stop is:

| Code | Question the stop becomes | Answer type |
|---|---|---|
| ROLE_UNKNOWN | Which of the 21 roles is this file? | pick 1 of 2–3 candidates |
| SLUG_UNKNOWN | What paper does this folder belong to? | pick from registered papers |
| KIND_UNKNOWN | Main / FAQ / audit / story / media / transcript? | pick 1 of closed list |
| DUPLICATE_DECLARED_ID | Which file is which edition? | **David only — goes straight to rung 4** |
| FAQ_NAME_MISMATCH | Does this FAQ belong to this paper? | yes / no |
| SCRIPTURE_UNVERIFIED | Is this phrase an allusion to that verse? | yes / no |
| ROOT_STUB | Is this a stub of that paper? | yes / no |

Where the script stops is not where the program stops: the stop only hands the question to rung 1.

**Authority codes skip the ladder.** Anything about canon, standing or which duplicate wins goes directly to rung 4. No model gets a vote on those.

### Rung 1 — Jev, as a binary or closed choice

Every stop is reframed as the smallest question that settles it: yes/no, or one of the 2–3 candidates the script already narrowed down. Never an open "what is this?" Jev answers with a choice and a confidence. If confidence is above the question type's trusted threshold (see Accuracy), the answer is proposed. Otherwise it climbs.

### Rung 2 — the blind pair

Two independent calls. Blind means:
- neither sees the other's answer, Jev's answer, or the script's guess;
- the options are shuffled and relabelled each call, so neither can lean on order;
- the two prompts are worded differently (same facts, different frame).

Both must give the same answer. Repeat up to **3 rounds** with fresh shuffles. Accept only if the pair agrees in every round it ran and the question type's trusted accuracy is met. Any split climbs. The point is that agreement can't come from predicting the expected answer: there is nothing to predict from.

### Rung 3 — DeepSeek with a bundle

DeepSeek gets a compact bundle (Linked Record standard §14): the file's header and first lines, its folder listing, its neighbours' names and roles, the paper's front door and paper key, and the exact question with candidates. It reports what it used and what it couldn't see. Its answer is proposed only if it names its evidence. Otherwise it goes to rung 4.

### Rung 4 — leave it

Unresolved items stay in a visible queue with everything each rung said. We fill them in when we get to them. No rung retries forever.

## Accuracy: how a rung earns trust

The prediction engine (Prediction_GUI, Rule Brick predictions) keeps a score per **question type per rung**:

1. **Calibration set.** Items whose answers we already know (MIM's 21 main papers and FAQs, files David has approved). Every rung is run on these blind; its hit rate is recorded.
2. **Threshold.** A rung's answer for a question type is proposed only if that rung's hit rate on that type is at least **90%** (tunable). Below that, its answers are logged as predictions but the question still climbs.
3. **Learning.** Every David approval or rejection is an outcome. Hit rates update; a rung can earn or lose trust per question type. Learning never changes the principles or anyone's canon status (Rule Brick 10).

## Running it over all of Obsidian

- The namer and paper key fill a **queue** of stop codes; the loop drains it in the background (Rust Idle Runner when David is away).
- Parallel up to 30 calls (David's rule). Budget cap per run and a stop rule set before starting.
- Every rung writes a receipt: item, question, rung, model, prompt version, inputs hash, answer, confidence, cost.
- Output is one review sheet: proposed answers grouped by confidence, plus the unresolved queue. David approves in bulk or one by one.

## What is not decided here

- Who "Jeff" is: drafted as **Jev** (TypeSafe classifier). Correct if it's a different engine.
- Threshold values per question type.
- Which model the blind pair uses (same as Jev, or a second cheap model for independence).
- Where the queue lives (David-OSv3 SQLite is the natural home; single writer only).

## Build order

1. Stop-code list as one shared module; 106 namer and paper key emit it (namer already emits most of these as flags).
2. Calibration set from MIM (known answers).
3. Rung 1 + rung 2 runner with blind shuffling and receipts; measure hit rates on the calibration set before trusting anything.
4. Rung 3 bundle builder.
5. Queue + review sheet; then background running over Obsidian.
