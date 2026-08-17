---
title: "LLM Wiki Exploration Schema"
uuid: "schema-llm-wiki-001"
date_created: "2026-07-06T00:00:00Z"
status: "canonical"
tags: [system/schema, system/llm-wiki]
---

# LLM Wiki Exploration Schema
## Theophysics Production Vault

**READ THIS FIRST.** This is the operating manual for the exploration layer.
Any AI session that wants to do exploration work reads this, reads the
SQLite index, picks a page, and goes.

---

## What This Is

An autonomous research layer on top of the Theophysics corpus.
You read an existing page. You go out into the world and do original
research against it. You write up what you found. You log it in SQLite.
You move to the next page. No human curation required.

The goal is density — hundreds to thousands of research notes that
probe, connect, break, validate, and extend the framework from every
angle. The corpus gets smarter over time without David touching it.

---

## Folder Structure

```
O:\_Theophysics_v5\
  _EXPLORATIONS\
    SCHEMA.md                    ← you are here
    index\                       ← Dataview-friendly index pages
    by_parent\                   ← explorations mirroring parent paths
      00_AXIOMS\
        A1.1_Existence\
          BREAK_001.md
          CONNECT_001.md
          LATERAL_001.md
      04_THEOPHYSICS\
        ...

D:\DONT TOUCH BOOT UP\llm-wiki.db  ← SQLite index
```

Explorations mirror the parent's vault path under `by_parent\`.
This means Obsidian graph view shows the research web naturally.

---

## Exploration Types

These are loose categories, not rigid constraints. The runner rotates
through them weighted by what the parent page hasn't had yet.

| Type | Code | What It Does |
|------|------|-------------|
| Break Attempt | BREAK | Try to falsify the claim. Name the failure mode. If it holds, explain what should break it but doesn't. |
| Unseen Connection | CONNECT | Find a structural bridge to something outside the framework — another field, another paper, another tradition. Must survive /PROBE. |
| Supporting Evidence | SUPPORT | Find external evidence that independently validates. Peer-reviewed preferred. |
| Counter-Evidence | COUNTER | Find the strongest published objection or contradicting result. Steelman it. |
| Lateral | LATERAL | Something nobody would think to look for. Unconstrained. Follow whatever thread the page opens that isn't obvious. |
| Related Theory | THEORY | Find an existing theory, model, or framework that helps, extends, or conflicts. |
| Anti-Pattern | ANTI | Inverse of any type above. Anti-support = evidence that weakens. Anti-connect = apparent bridge that doesn't hold. Anti-theory = theory that seems related but isn't. |

The LATERAL type is explicitly unconstrained — no category, no expectation.
That's where the surprising stuff comes from.

---

## Exploration Page Format

Every exploration is a standalone markdown page with YAML frontmatter:

```yaml
---
title: "BREAK_001: Conservation symmetry challenge to A1.1"
uuid: "auto-generate"
date_created: "2026-07-06T12:00:00Z"
status: "complete"
tags: [exploration/break, parent/00_AXIOMS/A1.1_Existence]
exploration:
  type: BREAK
  parent_path: "00_AXIOMS/A1.1_Existence.md"
  parent_title: "A1.1 Existence"
  sequence: 1
  verdict: held | broke | inconclusive | new_connection | flagged
  confidence: 0.0-1.0
  summary_oneline: "Noether symmetry argument doesn't break Existence axiom because..."
---

# BREAK_001: Conservation symmetry challenge to A1.1

## Parent Claim
[Quote or paraphrase the specific claim being tested]

## Method
[How this exploration was conducted — what was searched, what was reasoned through]

## Findings
[The actual research — what was found, what it means]

## Verdict
[held / broke / inconclusive / new_connection / flagged]
[Why this verdict]

## Links
- Parent: [[A1.1_Existence]]
- Related explorations: [[...]]
- External sources: [citations]
```

---

## SQLite Database Schema

Location: `D:\DONT TOUCH BOOT UP\llm-wiki.db`

### Table: pages
Indexes every page in the corpus that can be explored.

```sql
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vault_path TEXT UNIQUE NOT NULL,      -- relative to vault root
    title TEXT,
    classification TEXT,                   -- axiom, theorem, claim, etc.
    tier INTEGER,                          -- 1-5
    tags TEXT,                             -- JSON array
    exploration_count INTEGER DEFAULT 0,
    last_explored TEXT,                    -- ISO datetime
    priority REAL DEFAULT 0.5             -- 0.0-1.0, higher = explore sooner
);
```

### Table: explorations
Every exploration that's been completed.

```sql
CREATE TABLE IF NOT EXISTS explorations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    type TEXT NOT NULL,                    -- BREAK, CONNECT, SUPPORT, etc.
    sequence INTEGER NOT NULL,             -- 1, 2, 3... per type per page
    verdict TEXT,                          -- held, broke, inconclusive, new_connection, flagged
    confidence REAL,
    summary TEXT,                          -- one-line summary
    file_path TEXT,                        -- path to the markdown file
    created_at TEXT NOT NULL,              -- ISO datetime
    session_id TEXT,                       -- which AI session did this
    FOREIGN KEY (page_id) REFERENCES pages(id)
);
```

### Table: queue
Pages that haven't been fully explored yet, with next recommended type.

```sql
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    next_type TEXT NOT NULL,               -- recommended next exploration type
    reason TEXT,                           -- why this type was chosen
    priority REAL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    FOREIGN KEY (page_id) REFERENCES pages(id)
);
```

---

## Runner Protocol

Any AI session doing exploration work follows this sequence:

1. **Read SCHEMA.md** (this file)
2. **Open SQLite** at `D:\DONT TOUCH BOOT UP\llm-wiki.db`
3. **Check queue** — pick the highest priority item, or if queue is empty:
   a. Find the page with the lowest `exploration_count`
   b. Pick the exploration type that page hasn't had yet
   c. Weight toward BREAK and CONNECT early, LATERAL and ANTI later
4. **Read the parent page** from the vault
5. **Do the research** — web search, cross-corpus reading, reasoning
6. **Write the exploration page** to `_EXPLORATIONS/by_parent/[mirrored path]/`
7. **Log in SQLite** — insert into explorations, update pages.exploration_count
8. **Populate queue** — suggest next exploration type for this page and others
9. **Repeat** until session ends or David redirects

### Rotation Logic

For a fresh page (0 explorations), default order:
BREAK → CONNECT → SUPPORT → COUNTER → THEORY → LATERAL → ANTI

After first pass, rotate freely. Weight toward types with fewer entries
across the whole corpus (if LATERAL is globally underrepresented, do more).

### When To Flag For David

- verdict = "broke" (something actually broke)
- verdict = "new_connection" with confidence > 0.8 (strong new bridge found)
- Any LATERAL that produces something genuinely surprising
- Contradictions between explorations on different pages

Flagged items get `flagged: true` in YAML and a row in a Dataview-queryable index.

---

## Dataview Integration

Add this query to any vault page to see its explorations:

```dataview
TABLE exploration.type AS "Type", exploration.verdict AS "Verdict",
      exploration.confidence AS "Conf", exploration.summary_oneline AS "Summary"
FROM "_EXPLORATIONS"
WHERE exploration.parent_path = this.file.path
SORT exploration.sequence ASC
```

Global dashboard query (put in `_EXPLORATIONS/index/DASHBOARD.md`):

```dataview
TABLE exploration.parent_title AS "Parent", exploration.type AS "Type",
      exploration.verdict AS "Verdict", exploration.confidence AS "Conf"
FROM "_EXPLORATIONS"
WHERE exploration.verdict = "broke" OR exploration.verdict = "new_connection"
SORT exploration.confidence DESC
```

---

## OKF Compliance

Every page in this system (parent or exploration) follows Open Knowledge Format:
- Identity = file path
- Metadata = YAML frontmatter
- Content = markdown body
- Links = wikilinks (Obsidian-native)

The entire vault is portable. Move the folder, the knowledge moves with it.
The SQLite database is the index, not the truth — it can be rebuilt from
the markdown files at any time by scanning YAML frontmatter.

---

## What This Is NOT

- Not a maintenance layer (no cleanup, no deduplication, no reformatting)
- Not a summary system (no paraphrasing existing content)
- Not constrained to the framework's own claims (go outside, find what's real)
- Not requiring David's approval to run (just go)

---

*Schema v1.0 | July 6, 2026 | David Lowe / Opus*
