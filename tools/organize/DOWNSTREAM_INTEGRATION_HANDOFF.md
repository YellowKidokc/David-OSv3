# FIS ↔ PPK ↔ Organize: Downstream Integration Handoff
**From: Opus (Claude) — 2026-06-03**
**For: Any AI picking up FIS/PPK/Organize work**
**Context: This was worked out with David in conversation. The GUI builder doesn't have this context yet.**

---

## THE GAP: PPK Learn Loop Is Not Closed

The forward path works: `pipeline.process()` → `attach_ppk_manifest()` → `PPK.predict()`. Every classify call generates route predictions.

**But `/approve` never calls `PPK.learn()`.** When David accepts a rename, the file gets renamed and that's it. The accept/reject decision never flows back as a reward signal. This is why all PPK predictions are uniform zeros at 0.125 confidence — the kernel has literally never received a learn event.

### The fix (in `fis/api.py`, `/approve` endpoint):

After the rename succeeds, pull the PPK manifest that was stored during classify, extract the features, and call:
```python
kernel.learn(features, action=f"route:{accepted_station}", reward=1.0)
```

Add a `/reject` endpoint that does the same with `reward=-1.0`.

This is ~15 lines in api.py. Without this, the entire preference system is architecturally complete but functionally inert.

---

## DESIGN DECISION: SQLite WAL Event Log (Async Learning)

David doesn't want PPK learning to slow down the classify pipeline. The design:

### Current (synchronous, blocks API response):
```
file → extract → NLP → classify → Postgres → PPK predict → PPK manifest → respond
```

### New (async, non-blocking):
```
HOT PATH (blocks response):
  file → extract → NLP → classify → Postgres → respond
  + append event to SQLite (WAL mode, <1ms)

BACKGROUND WORKER (nobody waiting):
  reads unprocessed events from SQLite every few seconds
  → builds artifact manifest
  → runs PPK predict
  → on approve/reject: runs PPK learn
  → marks event processed
```

### SQLite schema:
```sql
CREATE TABLE IF NOT EXISTS fis_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,  -- 'classify', 'approve', 'reject', 'recall', 'clipboard', 'web'
    file_path   TEXT,
    features    TEXT,           -- JSON blob
    fis_result  TEXT,           -- JSON blob
    status      TEXT DEFAULT 'pending',  -- 'pending', 'processed', 'failed'
    created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    processed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_fis_events_status ON fis_events(status);
```

### Why SQLite not Postgres for this:
- No network hop (FIS and the event log are same machine)
- WAL mode = reads don't block writes, crash-safe atomic writes
- Single file, portable (like PPK model itself)
- It's the event tape, not the source of truth — Postgres stays canonical for files/tags

---

## DESIGN DECISION: Single Port Architecture

Everything runs on port 8420. No new servers, no new processes. Just route namespaces:

```
Port 8420 (FIS — the front door)
├── /classify          ← file classification (WORKS)
├── /approve           ← rename approval (WORKS but needs learn hook)
├── /reject            ← NEW: rejection signal + PPK learn(reward=-1)
├── /pending           ← pending queue (WORKS)
├── /search            ← file search (WORKS)
├── /tag               ← manual tagging (WORKS)
├── /bil/learn         ← behavioral signal (WORKS)
├── /bil/predict       ← relevance prediction (WORKS)
├── /bil/web           ← browser extension (WORKS)
├── /bil/clipboard     ← clipboard watcher (WORKS)
├── /bil/recall        ← NEW: OpenRecall screen captures
├── /ppk/learn         ← NEW: direct PPK teach endpoint
├── /ppk/predict       ← NEW: direct PPK route query
├── /ppk/summary       ← NEW: export model summary
├── /health            ← health check (WORKS)
└── /bil/export        ← daily digest (WORKS)
```

---

## OPENRECALL INTEGRATION

OpenRecall (open-source Windows Recall alternative) is downloaded at:
```
C:\Users\lowes\Downloads\openrecall-main\openrecall-main\
```

It takes periodic screenshots, OCRs text, stores in its own SQLite with columns:
`id, app, title, text, timestamp, embedding`

Integration approach: a bridge script watches OpenRecall's SQLite for new entries and POSTs to `/bil/recall` on 8420. Or add a hook in OpenRecall's `app.py` after each capture.

The FIS side just needs the `/bil/recall` endpoint that:
1. Extracts features from {app, title, text, timestamp}
2. Appends to the SQLite event log
3. Background worker processes it through BIL/River

Same pattern as `/bil/web` and `/bil/clipboard` — just a third behavioral input stream.

---

## PREFERENCE ENGINE CHAIN — HOW THE MODELS CONNECT

This is the critical part. The models are NOT independent — they wire into each other
in a specific order. If you don't understand this chain, you'll wire things wrong.

### The chain (data flows downward):

```
INPUT STREAMS (browser, clipboard, OpenRecall, file classify)
       │
       ▼
┌─────────────────────────────────────────────┐
│  RIVER (Model 18) — the small fast one      │
│  Library: river v0.25.0                     │
│  What it does: Online streaming ML          │
│  Speed: Microsecond latency per event       │
│  Location: Inside BIL server on port 8420   │
│  Status: PARTIALLY WIRED via /bil/* routes  │
│                                             │
│  River processes every behavioral event     │
│  in real-time. One event at a time.         │
│  It is the LEARNING ENGINE.                 │
└──────────────────┬──────────────────────────┘
                   │ River's learned weights get
                   │ compressed into ↓
                   ▼
┌─────────────────────────────────────────────┐
│  PPK (Model 17) — the portable output       │
│  Script: portable_preference_kernel.py      │
│  What it does: Stores preference weights    │
│  Size: Tiny JSON file, kilobytes            │
│  Location: _ppk_runtime/ in FIS station     │
│  Status: PREDICT works. LEARN NOT WIRED.    │
│                                             │
│  PPK is NOT a learning engine.              │
│  PPK is the PORTABLE EXPORT of what River   │
│  learned. Copy this file to any machine     │
│  and another FIS/AI worker knows David's    │
│  preferences without needing River's        │
│  full state.                                │
│                                             │
│  River README says it explicitly:           │
│  "River is the learning engine.             │
│   PPK is the portable output.              │
│   BIL/River collects signals →             │
│   PPK stores portable preference identity." │
└──────────────────┬──────────────────────────┘
                   │ PPK's accumulated routing
                   │ decisions feed ↓
                   ▼
┌─────────────────────────────────────────────┐
│  IMPLICIT (Model 13) — collaborative filter │
│  Library: implicit (ALS, BPR, logistic MF)  │
│  What it does: Learns station co-occurrence │
│  Example: "David always runs claim-extractor│
│  THEN paper-proof-grader on the same file"  │
│  → recommends the second station before     │
│  David asks.                                │
│  Status: INSTALLED, NOT YET WIRED           │
│  Needs: PPK training data first (PPK must   │
│  have real learned weights before Implicit   │
│  can learn co-occurrence from them)          │
└─────────────────────────────────────────────┘

### Separate specialist (not in the main chain):

┌─────────────────────────────────────────────┐
│  MARKOVIFY (Model 19) — text prediction     │
│  What it does: Markov chain text generation │
│  Use case: "David would say..." autocomplete│
│  Needs: Training corpus (clipboard JSONL +  │
│  vault text)                                │
│  Status: INSTALLED, NOT YET WIRED           │
│  This is independent — it doesn't feed from │
│  or into the River→PPK→Implicit chain.      │
└─────────────────────────────────────────────┘
```

### Wiring priority (in order):

1. **Close the PPK learn loop** — `/approve` must call `PPK.learn()`. Without this, River has no portable output target and Implicit has no data to learn from. THE critical gap.
2. **SQLite event log + background worker** — decouple learning from the hot path so classify stays fast.
3. **OpenRecall bridge** — third input stream feeding River, same pattern as browser/clipboard.
4. **Implicit (13)** — only wire AFTER PPK has accumulated real training data from the learn loop. Wiring it now with zero-weight PPK data is pointless.
5. **Markovify (19)** — independent, can be wired anytime a training corpus is prepared.

### Model locations:
```
\\dlowenas\brain\Backside\_models\_Models\17_portable_preference_kernel\
\\dlowenas\brain\Backside\_models\_Models\13_preference_implicit\
\\dlowenas\brain\Backside\_models\_Models\18_river_streaming\
\\dlowenas\brain\Backside\_models\_Models\19_markovify_text\
```

---

## CLIPBOARD ARCHITECTURE — WHAT EXISTS AND WHAT'S MISSING

David has MULTIPLE clipboard systems. Here's what's live and how they connect:

### Active systems:

```
1. CLIPSYNC (PWA on Edge — the one David actually uses)
   Location: D:\ClipSync\
   Backend:  Cloudflare Worker at clipsync.faiththruphysics.com
   Storage:  Cloudflare KV (clips, prompts, bookmarks)
   Features: Clips, Prompts, Bookmarks, TTS, search, dark theme
   AHK:      D:\ClipSync\clipsync-hotkeys.ahk (monitors clipboard, POSTs to ClipSync API)
   Status:   LIVE, installed as PWA with desktop icon

2. BIL CLIPBOARD WATCHER (Python — feeds FIS)
   Location: D:\BIL\clipboard_watcher.py
   Endpoint: POST http://localhost:8420/bil/clipboard
   Log:      D:\BIL\data\clipboard\clipboard_watcher.jsonl
   Status:   WORKS when FIS is running on 8420

3. BIL BROWSER EXTENSION (Chrome — captures copy events in browser)
   Location: D:\BIL\browser\content.js
   Sends:    clipboard_text message to background.js → /bil/web
   Status:   WORKS but text-only (uses getSelection().toString())

4. NERVE (Rust — clipboard + hotstrings + TTS)
   Location: D:\Clipboard sync\
   Crate:    clipboard-win (CAN access CF_HTML but currently reads Unicode only)
   Status:   BUILT but secondary to ClipSync
```

### What NONE of them do:

**Capture HTML clipboard format.** Every path grabs text-only:
- ClipSync AHK: `A_Clipboard` → text
- clipboard_watcher.py: tkinter `clipboard_get()` → text
- Browser extension: `getSelection().toString()` → text
- Nerve: `formats::Unicode` → text (but has `formats::Html` available)

### The integration David wants:

```
ClipSync (PWA, what David uses)
    ↓ AHK pushes clip events
    ↓
FIS on 8420 (/bil/clipboard)
    ↓ SQLite event log
    ↓
┌───────────────────────────────────────┐
│ River (18) — real-time streaming      │
│ learns clipboard patterns instantly   │
│ "David copies code at 2am,            │
│  Bible verses in morning"             │
├───────────────────────────────────────┤
│ Implicit (13) — co-occurrence         │
│ "David always copies X then Y"        │
│ predicts Y when X is copied           │
├───────────────────────────────────────┤
│ Markovify (19) — text prediction      │
│ trains on clipboard JSONL + vault     │
│ "David would type..." completions     │
│ Training source already accumulating: │
│ D:\BIL\data\clipboard\               │
│   clipboard_watcher.jsonl             │
└───────────────────────────────────────┘
```

### HTML clipboard fix (when ready):

Easiest path: patch the browser extension's copy listener in content.js:
```javascript
const range = selection.getRangeAt(0);
const fragment = range.cloneContents();
const div = document.createElement('div');
div.appendChild(fragment);
const html = div.innerHTML;
// send both {text, html} to background
```

Second path: Nerve's clipboard.rs already has `clipboard-win` with `formats::Html` available — one function addition.

---

## ORGANIZE GUI STATUS

As of this session, the GUI has 5 tabs:
- Quick Sort, Workflow Builder, File Intelligence, History, Settings
- Dark theme applied, threshold gate wired, folder UUIDs via .orgledger
- File Intelligence auto-detects FIS on 8420 — works offline until FIS is live
- Launch: `D:\GitHub\organize\LAUNCH_GUI.bat`

---

## STANDING RULES

- Everything shares port 8420. No new servers.
- SQLite WAL for the event log. Postgres stays canonical for files/tags.
- PPK model file stays portable (copy to any machine).
- Backside model folders are READ-ONLY unless David explicitly opens a migration lane.
- Run `python tools\backside_audit.py --note "before <change>"` before any behavior change.
