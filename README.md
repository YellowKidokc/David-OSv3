# David-OS
## Unified Infrastructure for Theophysics Production

One system. Everything runs from here.

### Architecture

```
David-OS/
├── core/           ← System config, schemas, standards
├── pipeline/       ← Chat-to-Vault processing (export → segment → cut → score → vault)
├── llm-wiki/       ← Autonomous exploration layer (SCHEMA, RUNNER, SQLite init)
├── scoring/        ← 1-2-3 intensity scoring system + auto-scorer
├── ahk/            ← AutoHotKey overlays (Claude.ai, Obsidian)
├── fis/            ← File Intelligence System
├── api/            ← Comms hub, Cloudflare Workers, bearer token endpoints
├── tagger/         ← YAML frontmatter auto-tagger + OKF compliance
└── README.md
```

### Pipeline Flow

```
RAW EXPORT → PARSE → SEGMENT → CUT → SCORE → VAULT → EXPLORE
   (Codex)    (Codex)  (SBERT)  (NLP)  (1-2-3)  (copy)  (LLM Wiki)
```

### Components

**Chat-to-Vault Pipeline**
- `pipeline/chat_topic_segmenter.py` — SBERT topic segmentation
- `pipeline/chat_fat_cutter.py` — Strips filler, preserves substance, builds error ledger

**LLM Wiki Exploration Layer**
- `llm-wiki/init_llm_wiki_db.py` — SQLite database init + vault scanner
- Vault files: `O:\_Theophysics_v5\_EXPLORATIONS\SCHEMA.md`
- Vault files: `O:\_Theophysics_v5\_EXPLORATIONS\RUNNER.md`
- Vault files: `O:\_Theophysics_v5\_EXPLORATIONS\SCORING_STANDARD.md`
- Database: `D:\DONT TOUCH BOOT UP\llm-wiki.db` (25,686 pages indexed)

**Scoring System**
- 42 properties across 6 categories (WHO/WHAT/WHEN/WHERE/WHY/FRAMEWORK)
- 1-2-3 intensity scoring (3=primary, 2=present, 1=touched, 0=absent)
- Inter-rater reliability test: ±1 convergence between scorers
- Auto-scorer applies scores by reading page content

**Infrastructure**
- AHK overlays for Claude.ai
- FIS (File Intelligence System)
- Comms hub API (comms.dlowehomelab.com)
- Tagger for YAML frontmatter + OKF compliance

### Deployment Target
- Local: Windows (D:\GitHub\David-OS)
- NAS: Synology (elevated permissions package)
- The exploration layer runs autonomously on Synology once deployed

### Standards
- OKF (Open Knowledge Format) compliant — markdown + YAML + path-as-identity
- Scoring Standard v1.0 — canonical reference in `core/SCORING_STANDARD.md`
- All output is Obsidian-native (wikilinks, Dataview-queryable)

---
*David Lowe | POF 2828 | July 6, 2026*
