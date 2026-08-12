---

  "fis_schema": "fisnote.v2",
  "op": "gov",
  "folder": "fis-atlas",
  "path": "D:\\GitHub\\David-OS\\fis-atlas",
  "generated_at": "2026-08-12T21:38:51+00:00",
  "purpose": "programming folder — 2 items, mostly markdown; behaves like project.",
  "folder_class": "programming",
  "class_confidence": 0.9,
  "class_evidence": [
    "program markers: ['run_atlas.py']"
  ],
  "risk": "red",
  "red_flags": [
    "program_root"
  ],
  "allowed_actions": [
    "tag",
    "report",
    "protect"
  ],
  "forbidden_actions": [
    "move",
    "rename",
    "delete",
    "archive",
    "publish"
  ],
  "behaves_like": "project",
  "direct_children": 7,
  "total_descendants": 48,
  "total_size": 4119,
  "type_distribution": {
    "markdown": 1,
    "code": 1
  },
  "move_breaks_relationships": false,
  "node": {
    "watch": false,
    "on_new_file": [
      "und/classify",
      "dec/normalize_name"
    ],
    "notify": {
      "when": "new_file",
      "channel": "toast"
    }
  }
---

# FIS Node: fis-atlas
**What this is:** programming folder — 2 items, mostly markdown; behaves like project.
**Type:** programming · **Risk:** 🔴 red · **You may:** tag, report, protect
**Never:** move, rename, delete, archive, publish

## Direct files (description · role · activity · event ledger)
- `README.md` :: markdown · reference · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved
- `run_atlas.py` :: code · project_file · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved

<!-- fisnote.v2 — parseable, safe to regenerate. -->