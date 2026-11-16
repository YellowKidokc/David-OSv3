"""YouTube dossier -> select -> evaluate -> FAQ draft, for every MIM paper.
Written by Claude (chat), Nov 13, 2026. Standard library only. Reads DEEPSEEK_API_KEY from env.
Never overwrites: writes new files into <paper>/.data/api/ (created if missing).
Usage: python youtube_dossier_eval.py [paper_numbers...]   (default: 00 and 02-20)
"""
from shared.runtime_config import path_setting as _portable_path
from pathlib import Path as _PortablePath
import os, sys, json, re, glob, time, threading, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

ROOT = str(_portable_path('DAVID_OS_LEGACY_YOUTUBE_DOSSIER_EVAL_MIM', 'legacy_youtube_dossier_eval_mim', _PortablePath(__file__).resolve().parents[1] / '_local/MIM'))
KEY = os.environ.get("DEEPSEEK_API_KEY")
MODEL = "deepseek-chat"
PRICE_IN, PRICE_OUT = 0.27 / 1e6, 1.10 / 1e6   # USD per token, approx
CAP_USD = 5.0
spent = 0.0
lock = threading.Lock()
TODAY = date.today()
STAMP = f"{TODAY:%y}.api.{TODAY:%m_%d}"

def call(messages, max_tokens=4000, json_mode=False):
    global spent
    with lock:
        if spent >= CAP_USD:
            raise RuntimeError("spend cap reached")
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request("https://api.deepseek.com/chat/completions",
        data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
            u = d.get("usage", {})
            cost = u.get("prompt_tokens", 0) * PRICE_IN + u.get("completion_tokens", 0) * PRICE_OUT
            with lock:
                spent += cost
            return d["choices"][0]["message"]["content"], u, cost
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))

def read(p, n=None):
    try:
        t = open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""
    return t[:n] if n else t

def paper_files(num):
    d = glob.glob(os.path.join(ROOT, f"{num}_MIM.{num}_*"))
    if not d:
        return None
    d = d[0]
    mains = [p for p in glob.glob(os.path.join(d, f"MIM.{num}.*.md"))]
    paper = max(mains, key=os.path.getsize) if mains else None
    tx = {}
    for p in glob.glob(os.path.join(d, "research", "youtube_transcript", "**", "*.md"), recursive=True):
        name = os.path.basename(p)
        if name not in tx or os.path.getsize(p) > os.path.getsize(tx[name]):
            tx[name] = p
    return d, paper, tx

SELECT_SYS = """You select research transcripts for one paper. The paper's load-bearing claim and boundary card are given.
Pick the 5-7 transcripts that bear DIRECTLY on the load-bearing claim. At least 2 must ATTACK or seriously challenge it.
Reject keyword overlap. Return JSON: {"selected":[{"file":..., "reason":..., "stance":"support|bridge|attack"}], "rejected_note": "one line on why the rest were cut", "harvest_quality":"good|mixed|mostly_noise"}"""

EVAL_SYS = """You are an epistemic auditor for one paper in David Lowe's Math Is Moral series.
First state the paper's load-bearing claim in one sentence. Then for EACH transcript:
## YT_n — SPEAKER/CHANNEL: "Title"
1. Core Relevance: GENUINE or KEYWORD-ADJACENT, and which slice is the gold (quote the speaker exactly, short).
2. Epistemic Role: SUPPORTING WITNESS / BRIDGE CONCEPT / ADVERSARIAL OBJECTION.
3. Actionable Recommendations: which exact sentence or section of the paper it bears on (quote it); the insight to incorporate; a suggested one-sentence use; Blast radius LOW/MODERATE/HIGH with mitigation.
Hunt hardest for transcripts that ATTACK the paper; they are the most valuable. Never let a citation claim past the paper's boundary card.
End with a SUMMARY TABLE (Transcript | Relevance | Role | Blast Radius | Verdict) and a BOTTOM LINE FOR THE AUTHOR paragraph.
Quote speakers only with words that actually appear in the transcript text given."""

FAQ_SYS = """Write an FAQ companion for this paper from the evaluation provided, modeled exactly on the example FAQ given.
Rules: questions in quotes are what real people ask. When an answer responds to a named creator or scholar, put a short italic line above the answer naming them, the video, and their argument in their own words (quote exactly from the evaluation's quotes only; if unsure, paraphrase and add [verify quote]). Steelman them. Concede out loud whatever they get right. Never mock. Answers are in the paper's plain declaration voice: short sentences, no hedging, never claim past the paper's boundary card. 5-8 questions. Finish with an internal source note (not for publication) listing which transcript prompted each question.
Start with YAML frontmatter: id "<ID>.FAQ", title, series MIM, type faq, parent "[[<ID>]]", standing draft."""

def run(num):
    got = paper_files(num)
    if not got or not got[1]:
        return {"paper": num, "status": "no paper file"}
    d, paper_path, tx = got
    pid = os.path.basename(paper_path)[:-3]
    out = os.path.join(d, ".data", "api")
    os.makedirs(out, exist_ok=True)
    base = os.path.join(out, f"{pid}__{STAMP}.YOUT.0001")
    if os.path.exists(base + ".md"):
        return {"paper": pid, "status": "already run, skipped"}
    paper = read(paper_path)
    card = paper[paper.rfind("## Card"):] if "## Card" in paper else paper[-3000:]
    if not tx:
        return {"paper": pid, "status": "no transcripts"}
    listing = "\n\n".join(f"FILE: {n}\n{read(p, 800)}" for n, p in sorted(tx.items()))
    sel_txt, u1, c1 = call([{"role": "system", "content": SELECT_SYS},
        {"role": "user", "content": f"PAPER ID: {pid}\nPAPER CARD AND BOUNDARY:\n{card}\n\nPAPER OPENING:\n{paper[:3000]}\n\nTRANSCRIPTS (first 800 chars each):\n{listing[:180000]}"}],
        max_tokens=1500, json_mode=True)
    sel = json.loads(sel_txt)
    chosen = [s for s in sel.get("selected", []) if s.get("file") in tx][:7]
    bundle = "\n\n".join(f"=== YT_{i+1}: {s['file']} (stance guess: {s.get('stance')}) ===\n{read(tx[s['file']], 9000)}" for i, s in enumerate(chosen))
    ev, u2, c2 = call([{"role": "system", "content": EVAL_SYS},
        {"role": "user", "content": f"PAPER {pid} (full text):\n{paper[:20000]}\n\nTRANSCRIPTS:\n{bundle}"}], max_tokens=5000)
    header = f"# DeepSeek Evaluation: YouTube dossier for {pid}\n\n**Date:** {TODAY}  \n**Model:** {MODEL}  \n**Selected:** {len(chosen)} of {len(tx)} transcripts  \n**Harvest quality:** {sel.get('harvest_quality')}  \n\n---\n\n"
    open(base + ".md", "w", encoding="utf-8").write(header + ev)
    example = read(os.path.join(ROOT, "01_MIM.01_Objective-Truth", "FAQ_MIM.01.TRUTH.md"))
    faq, u3, c3 = call([{"role": "system", "content": FAQ_SYS.replace("<ID>", pid)},
        {"role": "user", "content": f"EXAMPLE FAQ:\n{example}\n\nPAPER {pid}:\n{paper[:16000]}\n\nEVALUATION:\n{ev}"}], max_tokens=4000)
    faq_path = os.path.join(d, f"FAQ_{pid}.md")
    if os.path.exists(faq_path):
        faq_path = os.path.join(out, f"FAQ_{pid}__{STAMP}.draft.md")
    open(faq_path, "w", encoding="utf-8").write(faq.strip().removeprefix("```markdown").removesuffix("```").strip() + "\n")
    rec = {"paper": pid, "date": str(TODAY), "model": MODEL, "transcripts_total": len(tx),
           "selected": chosen, "rejected_note": sel.get("rejected_note"), "harvest_quality": sel.get("harvest_quality"),
           "cost_usd": round(c1 + c2 + c3, 4), "usage": [u1, u2, u3], "faq": faq_path}
    json.dump(rec, open(base + ".json", "w", encoding="utf-8"), indent=2)
    return {"paper": pid, "status": "done", "selected": len(chosen), "of": len(tx),
            "harvest": sel.get("harvest_quality"), "cost": rec["cost_usd"]}

if __name__ == "__main__":
    if not KEY:
        sys.exit("DEEPSEEK_API_KEY not set")
    nums = sys.argv[1:] or ["00"] + [f"{i:02d}" for i in range(2, 21)]
    def safe(n):
        try:
            r = run(n)
        except Exception as e:
            r = {"paper": n, "status": f"error: {e}"}
        print(json.dumps(r), flush=True)
        return r
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(safe, nums))
    summary = os.path.join(ROOT, f"YOUTUBE_RUN_SUMMARY_{TODAY:%Y-%m-%d}.json")
    json.dump({"results": results, "total_cost_usd": round(spent, 4)}, open(summary, "w", encoding="utf-8"), indent=2)
    print(f"TOTAL ${spent:.4f}  summary -> {summary}", flush=True)
