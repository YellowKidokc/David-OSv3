---

  "fis_schema": "fisnote.v2",
  "op": "gov",
  "folder": "handlers",
  "path": "D:\\GitHub\\David-OS\\fis-atlas\\fis\\handlers",
  "generated_at": "2026-08-12T21:38:51+00:00",
  "purpose": "programming folder — 3 items, mostly code; behaves like project.",
  "folder_class": "programming",
  "class_confidence": 0.9,
  "class_evidence": [
    "program markers: ['dec_normalize.py']"
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
  "direct_children": 4,
  "total_descendants": 7,
  "total_size": 1577,
  "type_distribution": {
    "code": 3
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

# FIS Node: handlers
**What this is:** programming folder — 3 items, mostly code; behaves like project.
**Type:** programming · **Risk:** 🔴 red · **You may:** tag, report, protect
**Never:** move, rename, delete, archive, publish

## Direct files (description · role · activity · event ledger)
- `__init__.py` :: code · project_file · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved
- `dec_normalize.py` :: code · project_file · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved
- `registry.py` :: code · project_file · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved

<!-- fisnote.v2 — parseable, safe to regenerate. -->