---

  "fis_schema": "fisnote.v2",
  "op": "gov",
  "folder": "tests",
  "path": "D:\\GitHub\\David-OS\\fis-atlas\\tests",
  "generated_at": "2026-08-12T21:38:51+00:00",
  "purpose": "programming folder — 2 items, mostly code; behaves like project.",
  "folder_class": "programming",
  "class_confidence": 0.9,
  "class_evidence": [
    "program markers: ['test_classify.py']"
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
  "direct_children": 3,
  "total_descendants": 5,
  "total_size": 4120,
  "type_distribution": {
    "code": 2
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

# FIS Node: tests
**What this is:** programming folder — 2 items, mostly code; behaves like project.
**Type:** programming · **Risk:** 🔴 red · **You may:** tag, report, protect
**Never:** move, rename, delete, archive, publish

## Direct files (description · role · activity · event ledger)
- `test_classify.py` :: code · project_file · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved
- `test_rules.py` :: code · project_file · recently_used · sens=unknown · treat=protect (class 0.85/act 0.95)
    - events: created … modified … opened … moved=not_moved

<!-- fisnote.v2 — parseable, safe to regenerate. -->