#!/usr/bin/env python3
"""FIS Approval GUI server — the mouth and hands for the naming pipeline.
POF 2828 | 2026-07-21

Serves the approval UI at http://127.0.0.1:10778 and bridges decisions into
the preference engine so every click makes the system smarter.

Contract (files live next to this script unless FIS_DATA_DIR env is set):
  fis_proposals.jsonl  — one proposal per line, written by fis_namer/daemon:
      {"id": "...", "path": "...", "current_name": "...", "proposed_name": "...",
       "folder_class": "...", "domain": "...", "ct": "...", "status": "...",
       "tags": [...], "confidence": 0.0-1.0, "ts": "..."}
  fis_decisions.jsonl  — appended by this server on every decision:
      {"id": "...", "decision": "approved|rejected|edited",
       "final_name": "...", "ts": "..."}

Decisions NEVER touch files on disk — observe/propose/approve only.
The separate executor (MovePlan flow) acts on approved decisions.

Run:  python server.py        then open http://127.0.0.1:10778
      (notify.ps1 raises a Windows toast that opens it for you)
"""
import json
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FIS_DATA_DIR", HERE))
PROPOSALS = DATA / "fis_proposals.jsonl"
DECISIONS = DATA / "fis_decisions.jsonl"
PORT = 10778

# Optional: live preference engine (learns on every decision)
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "engine"))
try:
    from preference.ensemble import get_ensemble
    ENGINE = get_ensemble()
except Exception:
    try:
        from fis_preference_engine import PreferenceEngine
        ENGINE = PreferenceEngine()
    except Exception:
        ENGINE = None

# Optional: X-drive Markov chains (P07) - second learner, fails silently offline
try:
    from fis_markov_bridge import record_decision as MARKOV_RECORD
except Exception:
    MARKOV_RECORD = None


def read_jsonl(p: Path):
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def pending():
    decided = {d.get("id") for d in read_jsonl(DECISIONS)}
    items = [p for p in read_jsonl(PROPOSALS) if p.get("id") not in decided]
    if ENGINE:
        for it in items:
            try:
                it["predicted_approval"] = round(ENGINE.predict(it), 3)
            except Exception:
                it["predicted_approval"] = None
    return items


def append_decision(prop: dict, decision: str, final_name: str | None = None):
    entry = {
        "id": prop.get("id"),
        "decision": decision,
        "final_name": final_name or prop.get("proposed_name"),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    with DECISIONS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    if MARKOV_RECORD:
        try:
            MARKOV_RECORD(prop, decision)
        except Exception:
            pass
    learned = False
    if ENGINE:
        try:
            ENGINE.learn(prop, approved=(decision != "rejected"))
            learned = True
        except Exception:
            pass
    return learned


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/proposals":
            items = pending()
            self._send(200, {"count": len(items), "proposals": items[:500],
                             "engine": bool(ENGINE)})
        elif self.path.startswith("/api/decide"):
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            pid = (qs.get("id") or [""])[0]
            decision = (qs.get("decision") or [""])[0]
            if decision not in ("approved", "rejected", "edited") or not pid:
                return self._send(400, {"error": "need id + decision"})
            prop = next((p for p in read_jsonl(PROPOSALS) if p.get("id") == pid), None)
            if prop:
                append_decision(prop, decision, (qs.get("final_name") or [None])[0])
            self._send(200, {"ok": True, "id": pid, "decision": decision})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/approve_all":
            items = pending()
            learned = False
            for prop in items:
                if prop.get("id"):
                    learned = append_decision(prop, "approved") or learned
            if ENGINE and learned:
                try:
                    ENGINE.save()
                except Exception:
                    pass
            return self._send(200, {"ok": True, "approved": len(items), "learned": learned})

        if self.path != "/api/decide":
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        pid = body.get("id")
        decision = body.get("decision")
        if decision not in ("approved", "rejected", "edited") or not pid:
            return self._send(400, {"error": "need id + decision"})
        prop = next((p for p in read_jsonl(PROPOSALS) if p.get("id") == pid), None)
        learned = False
        if prop:
            learned = append_decision(prop, decision, body.get("final_name"))
            if ENGINE and learned:
                try:
                    ENGINE.save()
                except Exception:
                    pass
        self._send(200, {"ok": True, "learned": learned})


if __name__ == "__main__":
    print(f"FIS Approval GUI -> http://127.0.0.1:{PORT}")
    print(f"proposals: {PROPOSALS}")
    print(f"decisions: {DECISIONS}")
    print(f"preference engine: {'LIVE (learning on every click)' if ENGINE else 'not loaded (decisions still ledgered)'}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
