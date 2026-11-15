# HUB SPEC — Providers, Prompt Types, Scheduler

POF 2828 | July 14, 2026 | Source: David voice notes, rewritten by Claude

---

## 1. PROVIDER REGISTRY (the "+")

No lock-in. Every AI is a row in `config/providers.json`:

```json
{
  "id": "ollama-local",
  "base_url": "http://127.0.0.1:11434/v1",
  "key": "",
  "model": "auto",
  "label": "Ollama",
  "priority": 100,
  "enabled": true,
  "auto_approved": true,
  "tags": ["local", "free"]
}
```

Any OpenAI-compatible endpoint works: Ollama, LM Studio, OpenAI, Anthropic via adapter, Kimi, Gemini proxy. The "+" in the GUI just appends a row. The Python service routes by provider id — one `send()` function, N brains.

Existing `config/services.ini` folds into this.

### Default providers (shipped)

| id | base_url | model | label | notes |
|---|---|---|---|---|
| `deepseek` | `https://api.deepseek.com` | `deepseek-v4-flash` | DeepSeek | Reads from env `DEEPSEEK_API_KEY` |
| `ollama-local` | `http://127.0.0.1:11434/v1` | `auto` | Ollama | Local, free, no key |
| `openai` | `https://api.openai.com/v1` | `gpt-4o` | OpenAI | Reads from env `OPENAI_API_KEY` |

### Rules

- Provider keys live in `config/providers.json` only, masked from any LLM call (same vault as paths/API keys).
- `auto_approved: true` means the scheduler can auto-send to this provider. **Never** set this on paid external APIs without explicit intent.
- `priority` determines fallback order when no provider is specified.
- `enabled: false` excludes the provider from routing without deleting its config.

---

## 2. THREE CONTENT TYPES (never one bucket)

### PROMPT
Single shot text. Fire and done.

Storage: `config/prompts/<id>.json`
```json
{
  "id": "morning-summary",
  "type": "prompt",
  "provider": "ollama-local",
  "content": "Summarize yesterday's clipboard items...",
  "tags": ["morning", "clipboard"]
}
```

### LOOP
Prompt + trigger + repeat + **EXIT CONDITION** (required field; a loop with no exit is a bug by definition).

Storage: `config/loops/<id>.json`
```json
{
  "id": "watch-folder",
  "type": "loop",
  "provider": "ollama-local",
  "prompt": "Check folder X for new files...",
  "trigger": "every-30s",
  "exit_condition": "folder-empty OR user-says-stop",
  "max_iterations": 100
}
```

### SKILL
Folder with instructions + resources (matches the skill format already in use). Skills can invoke prompts/loops.

Storage: `config/skills/<id>/SKILL.md` (same format as existing skills)

Each type gets its own tab and its own folder under `config/`.

---

## 3. SCHEDULER (the remembrance engine)

Triggers, all per-provider and per-user:

### SESSION WAKE
First message to an AI after N idle hours (default 2) → auto-send welcome/context pack first.

Context pack = who I am, active threads, unread comms summary. This automates the check-comms-first ritual — the machine does the liturgy.

### HOURLY ANCHOR
Every N minutes of active conversation → inject a remembrance prompt (posture/Q0 line, thread reminder, drift check).

### CLOCK
Cron-style — daily/weekly/once at HH:MM, run prompt/loop/skill against provider X.

Example: `"Every morning 6am: summarize yesterday's clips."`

---

## 4. RULES (Claude additions)

- **One scheduler**, in the Python service, reading `schedule.json`. AHK and HTML GUIs are faces only; timers never live in the GUI.
- Every fired event -> `ledger.jsonl` RunEvent (same lineage pattern as FIS).
- **QUIET HOURS** block auto-sends (default 23:00-06:00).
- **Kill switch**: one hotkey pauses all automation; status dot shows paused state.
- **Consent**: suggestion engines and consent never share a cell — scheduled sends to external paid APIs require a per-rule `auto_approved: true` set by hand in the config.
- **Jitter** ±2 min on clock triggers so five AIs don't stampede at once.

---

## 5. BUILD ORDER

| Step | What | Unlocks |
|---|---|---|
| 1 | `providers.json` + `send()` router in `services/provider_router.py` | The "+" button. Any OpenAI-compatible endpoint. |
| 2 | Split `prompts/`, `loops/`, `skills/` folders + GUI tabs | Three content types, each with its own UX. |
| 3 | `schedule.json` + tick loop (30s) + ledger logging | Automation starts working. |
| 4 | Session-wake welcome pack | Needs last-contact timestamp per provider. |
| 5 | Hourly anchor injection | Remembrance prompts while talking. |

---

## 6. ARCHITECTURE PRINCIPLE

One scheduler, in the Python service, nowhere else. The AHK hub and HTML pages are faces; if timers ever creep into three different GUIs you'll have ghost automations you can't find — the exact disease the FIS cleanout just cured.

**One brain, many faces.**

---

*David Lowe | POF 2828 | July 14, 2026*
