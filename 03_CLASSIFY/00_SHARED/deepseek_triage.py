"""DeepSeek triage — when a card is stuck, ask a model what's wrong and what the
value should be. It answers in JSON, can ask YOU a question back, and never
writes anything: its answer is one more suggestion in the review table, scored
by the ledger like every other engine.

Key: DEEPSEEK_API_KEY (environment). Model: deepseek-chat (override DEEPSEEK_MODEL).
Answers are cached in data/deepseek_cache.json by (card text, facet, your reply),
so asking twice about an unchanged card costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

URL = "https://api.deepseek.com/chat/completions"
ROOT = Path(__file__).resolve().parent          # 03_CLASSIFY/00_SHARED
CACHE = ROOT / "data" / "deepseek_cache.json"
_lock = threading.Lock()

SYSTEM = """You are the classification adjudicator for a research vault that follows TAG_TAXONOMY v0.4.
A sidecar card (mim.v1) describes one source paper. A review pipeline got stuck on this card or is unsure.
You get: the card text, the facet being decided, its closed list of allowed values, the problems the
validator found, and what each prediction engine suggested.

Rules:
- `value` MUST be one of the allowed values, or null if you cannot tell.
- Judge from the card's name and summary sentence, and from `source_paper` when it is given: that is
  the real paper (its opening and closing lines). The paper outranks the card's one-line summary.
  Status lines, version labels and words like "first pass", "draft", "proposal", "pending ruling",
  "declared", "frozen" are strong evidence. Do not invent facts the text does not show.
- standing meanings: declaration = fixes/declares something the framework treats as given; canon = human-ruled
  canonical (never propose unless the card says it was ruled); freeze-candidate = proposed for freeze;
  proposed = put forward, not ruled; draft = work in progress / first-pass / experimental;
  reference = lookup material with no claims; superseded = replaced by a newer source; inert = dead duplicate.
- If something is ambiguous, set needs_human=true and ask ONE short, specific question.
- If the human already answered a question (human_reply), use it.

Reply with JSON only:
{"stuck_at": "<which step/field is the real blocker, short>",
 "diagnosis": "<one or two sentences: what is wrong or unclear>",
 "value": "<allowed value or null>",
 "confidence": <0..1>,
 "reason": "<one sentence citing words from the card>",
 "needs_human": <true|false>,
 "question": "<one question for the human, or empty>"}"""


def api_key() -> str:
    """Same lookup as API/000_QUICK_CALL: environment first, then 03_CLASSIFY/00_SHARED/data/key.txt."""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key and (ROOT / "data" / "key.txt").exists():
        key = (ROOT / "data" / "key.txt").read_text(encoding="utf-8").strip()
    return key


def available() -> bool:
    return bool(api_key())


def _post(key: str, body: bytes, timeout: int) -> dict[str, Any]:
    """QUICK_CALL's retry rule: 429/5xx and network errors back off 2,4,8s; others fail at once."""
    for attempt in range(4):
        req = urllib.request.Request(URL, data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data["choices"][0].get("finish_reason") == "length":
                raise RuntimeError("reply hit the output-token limit; nothing saved")
            return data
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 3:
                raise RuntimeError(str(e)) from None
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("no answer")


def _cache_load() -> dict[str, Any]:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _cache_key(card_text: str, facet: str, human_reply: str) -> str:
    return hashlib.sha256(f"{facet}\n{human_reply}\n{card_text}".encode("utf-8")).hexdigest()[:24]


def strip_facet(card_text: str, facet: str) -> str:
    """Blind mode: remove the facet's current value from the card so the model has
    to decide from the summary, not copy the answer (it does copy, if allowed)."""
    out = []
    for line in card_text.replace("\r", "").split("\n"):
        s = line.strip()
        if facet in ("standing", "domain") and line.startswith(f"{facet}:"):
            continue
        if facet in ("standing",) and line.startswith("version:"):
            continue
        if facet not in ("standing", "domain") and s.startswith(f"- {facet}-"):
            continue
        out.append(line)
    return "\n".join(out)


def triage(card_text: str, facet: str, allowed: list[str], problems: list[str],
           engine_answers: list[str], human_reply: str = "", use_cache: bool = True,
           timeout: int = 60, blind: bool = False, paper: str = "") -> dict[str, Any]:
    """One call. Returns the parsed answer plus `_cached` / `_error` markers. Never raises.
    blind=True hides the current value and the engines' guesses: a real prediction."""
    if blind:
        card_text = strip_facet(card_text, facet)
        problems = [p for p in problems if facet not in p]
        engine_answers = []
    key = _cache_key(card_text + ("\n#paper\n" + paper if paper else ""), facet, human_reply)
    if use_cache:
        with _lock:
            hit = _cache_load().get(key)
        if hit:
            return {**hit, "_cached": True}
    key_ = api_key()
    if not key_:
        return {"_error": "no key: set DEEPSEEK_API_KEY or put it in 03_CLASSIFY/00_SHARED/data/key.txt"}
    user = {"facet": facet, "allowed_values": allowed, "validator_problems": problems,
            "engine_suggestions": engine_answers, "human_reply": human_reply, "card": card_text[:6000]}
    if paper:
        user["source_paper"] = paper[:12000]
    body = json.dumps({
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
        "temperature": 0, "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    try:
        payload = _post(key_, body, timeout)
        ans = json.loads(payload["choices"][0]["message"]["content"])
    except Exception as e:  # noqa: BLE001 — network, JSON, shape: report, don't crash the GUI
        return {"_error": f"{type(e).__name__}: {e}"}
    if ans.get("value") not in allowed:
        if ans.get("value"):
            ans["diagnosis"] = f"(model proposed off-list value {ans['value']!r}) " + str(ans.get("diagnosis", ""))
        ans["value"] = None
    try:
        ans["confidence"] = max(0.0, min(1.0, float(ans.get("confidence") or 0)))
    except (TypeError, ValueError):
        ans["confidence"] = 0.0
    usage = payload.get("usage", {})
    ans["_tokens"] = usage.get("total_tokens")
    with _lock:
        cache = _cache_load()
        cache[key] = ans
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    return {**ans, "_cached": False}
