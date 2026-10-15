# 01_PROFILE — the doorway wizard

The first step of the pipeline, before 03_CLASSIFY. Before the system touches a
folder, it needs to know what that folder *is* — personal or work, an Obsidian
vault or a code project, loose inbox or canonized final. This wizard asks the
questions once and writes the answers where everything downstream can read them.

## What it does

1. **Scans the folder read-only** (`profile_core.scan_evidence`) — Obsidian
   marker, project markers, extension histogram, file count.
2. **Pre-fills the 20 core questions** (`config/rules/onboarding_questions.v1.json`)
   from that evidence — suggestions are labeled with their source and confidence,
   and every suggestion is editable.
3. **Writes once, at the end** (`profile_core.write_profile`):
   - an entry in `config/folder_profiles.json` (role, approval floor, allowed /
     blocked / irrelevant actions) that the pre-flight gate (`engine/gate.py`)
     consults before every rename/move/delete;
   - a `.folder.fmeta` marker inside the folder — *unless* the folder is a
     project root (`.git`, `pyproject.toml`, …), which stays untouched.

Closing the window mid-run writes nothing. `write_profile` is the only disk
write in the whole step.

## Run it

```
PROFILE.bat "D:\path\to\folder"
```

or drag a folder onto `PROFILE.bat`, or run it bare and pick a folder.

## What it feeds

- `engine/gate.py` — verdicts (allow / preview / ask / block / drop) per action
  per folder, from the profile plus the rule JSONs in `config/rules/`.
- `03_CLASSIFY/03_RENAMING` — the renamer refuses rule-breaking batches and
  shows fired rules in the approval dialog; your overrides are logged as
  `gate_override` events the prediction harness learns from.
- Later steps (FIS reports, sidecar writers) read `sidecar_writer` /
  `report_type` from the same profile entry.
