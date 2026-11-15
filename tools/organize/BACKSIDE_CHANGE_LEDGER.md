# Backside Organize Change Ledger

This ledger records pre-change and post-change audit packets for the local organize source tree.

## Standing Boundary

- Log before behavior changes.
- Keep Backside model folders read-only unless David explicitly opens a migration lane.
- Use `17_portable_preference_kernel` as the first decision spine for this lane.
- Keep generated snapshots under `_backside_audit/`.

## Entries


### 2026-06-03T04:11:00+00:00

- Note: pre-change baseline in D:\GitHub\organize before organize behavior modifications
- Snapshot: `_backside_audit/snapshots/20260603T041100Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T041100Z_model_context.md`
- Source files: 154
- Source bytes: 1227848
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T04:11:33+00:00

- Note: pre-change baseline with PPK prediction handoff in D:\GitHub\organize
- Snapshot: `_backside_audit/snapshots/20260603T041132Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T041132Z_model_context.md`
- Source files: 154
- Source bytes: 1230849
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T04:12:02+00:00

- Note: pre-change baseline with successful UTF-8 PPK prediction handoff in D:\GitHub\organize
- Snapshot: `_backside_audit/snapshots/20260603T041202Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T041202Z_model_context.md`
- Source files: 154
- Source bytes: 1231537
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T04:35:35+00:00

- Note: before GUI launcher and first desktop organizer screen
- Snapshot: `_backside_audit/snapshots/20260603T043534Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T043534Z_model_context.md`
- Source files: 154
- Source bytes: 1232079
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T04:43:38+00:00

- Note: after GUI launcher and first desktop organizer screen
- Snapshot: `_backside_audit/snapshots/20260603T044338Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T044338Z_model_context.md`
- Source files: 162
- Source bytes: 1272673
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T04:59:10+00:00

- Note: before workflow builder: ignore-folders, pre-scan, extension groups, stages, save/load
- Snapshot: `_backside_audit/snapshots/20260603T045909Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T045909Z_model_context.md`
- Source files: 162
- Source bytes: 1273182
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T05:02:53+00:00

- Note: after workflow builder: ignore-folders, pre-scan extension picker, extension groups, multi-stage, save/load starters
- Snapshot: `_backside_audit/snapshots/20260603T050252Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T050252Z_model_context.md`
- Source files: 162
- Source bytes: 1307874
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T05:24:01+00:00

- Note: File Intelligence tab: FIS REST client (classify/approve), spreadsheet view name/proposed/certainty/status, select+apply, offline cleanup fallback
- Snapshot: `_backside_audit/snapshots/20260603T052400Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T052400Z_model_context.md`
- Source files: 163
- Source bytes: 1327309
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T05:37:57+00:00

- Note: History ledger: .orgledger plain-text logbooks (per-folder + master), stdlib polling watcher with move/rename/delete detection, History tab, WATCH_HISTORY.bat, run-at-login
- Snapshot: `_backside_audit/snapshots/20260603T053756Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T053756Z_model_context.md`
- Source files: 165
- Source bytes: 1354172
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T05:53:53+00:00

- Note: Settings tab + persisted NLP threshold (saving grace), renaming-process selector, folder UUID + NLP fingerprint stamped on the .orgledger paper
- Snapshot: `_backside_audit/snapshots/20260603T055353Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T055353Z_model_context.md`
- Source files: 166
- Source bytes: 1368402
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no

### 2026-06-03T05:56:17+00:00

- Note: Dark theme: blacked-out GUI (clam-based ttk styling, dark text/listboxes/trees, dark-friendly row tags, dark native title bar)
- Snapshot: `_backside_audit/snapshots/20260603T055616Z_organize_baseline.json`
- Context packet: `_backside_audit/context_packets/20260603T055616Z_model_context.md`
- Source files: 166
- Source bytes: 1374563
- Models inspected: 17_portable_preference_kernel (6 files), 13_preference_implicit (1 files), 18_river_streaming (1 files), 19_markovify_text (1 files)
- Behavior code changed by this audit: no
