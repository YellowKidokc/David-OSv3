# FIS Understand Pipeline — build spec

Source: David, 2026-09-16 (chat). Companion to the David-OS ethos brief (rules R1–R10).
Implementation: `engine/understand.py` → `.data/fis_understand.sqlite`.

## What it is
The first thing FIS does to any folder. Scans, stores everything in SQLite
(registry facts, tags, symptoms, duplicates, predictions, questions). **Not shown to
the end user** — it is the system's (and the AIs') understanding. GUIs read from it.

## Core rule
Record **observations** separately from **inferences**. Finding `.obsidian` is an
observation. "This folder is an Obsidian vault" is an inference supported by it.
Observation → Inference → Judgment → Authorization are four separate data classes (R3).
Nothing is moved, renamed, or deleted (R1). Predictions run in shadow mode until they
earn trust (R7).

## Stages
| # | Stage | Records |
|---|---|---|
| 1 | Inventory — walk selected roots, skip system/excluded dirs, no loops | files, skipped/unreadable + reason |
| 2 | Identify + extract — real format, text, headings, metadata | extraction method + errors |
| 3 | Exact copies — group by size, then SHA-256 | copy groups, every location kept |
| 4 | Classify documents — rules first, classifier/LLM for unresolved; multi-label + unknown | doc type, subjects, evidence, version, review status |
| 5 | Analyze folders — aggregate + structural markers | proposed purpose (kind/domain), composition, unusual files |
| 6 | Relationships — text similarity, ids, citations, structural overlap | candidate revision families / related docs / folder overlap |
| 7 | Completeness + authority — templates, approval records tied to hash | missing requirements, authority unresolved/conflicts |
| 8 | Propose actions — preview + approval | reviewable plan; execution writes audit record |

## Folder prediction (stage 5)
- Ground truth first: `config/folder_registry.yaml` (`confirmed: true` = never guessed).
- Kinds: code | documents | pictures | video | audio | data | mixed | needs_sorting.
- Domains: obsidian_vault, theophysics, trading, ai_chats, website, python/js project, …
- Labels coexist (a vault can also be research). Nested projects are separate collections;
  a marker deep inside must not relabel a whole drive.
- Always show the denominator: "420 of 530 files", not "mostly research".
- "Unusual" produces a review item, never an automatic move.

## When it doesn't understand
1. Ask David a question (questions table): "What is this folder?", with the prediction,
   evidence, and choices; answers are written back to folder_registry.yaml.
2. Optionally escalate to an API: send folder name, file names, extension mix (not file
   contents by default) and store the answer as an inference with source=llm.

## Authority
Canon comes only from explicit evidence: approval tied to a file hash, a canonical
registry (canon pins, canonical_186_sources.txt), or a supersession record. `FINAL` in a
name, dates, and location are clues only. Conflicts → "authority unresolved".

## Acceptance tests
- Recognizes a vault containing a nested software project.
- Finds identical files with different names.
- Keeps a revised document distinct from an exact duplicate.
- Reports unreadable files instead of silently excluding them.
- Leaves authority unresolved when approval evidence is absent.
- Produces proposed actions without changing source files.
