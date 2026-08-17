"""
report_builder.py — human-facing outputs from the inventory DB.

Produces:
  - approval_queue.csv : one row per proposed name, APPROVE column for the human
  - rename_plan.html   : readable dashboard (summary + proposals + folder symptoms)

Reads current state from SQLite. Writes nothing to user files.
"""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
import metadata_db as db


def write_csv(con, out_path: Optional[str] = None) -> str:
    out = Path(out_path or (config.REPORTS_DIR / "approval_queue.csv"))
    rows = db.all_proposed(con)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "path", "current_name", "proposed_name", "domain",
                    "content_type", "status", "confidence", "decision",
                    "context", "APPROVE", "notes"])
        for i, r in enumerate(rows, 1):
            context = r["notes"] or r["reason"] or ""
            w.writerow([i, r["path"], r["name"], r["proposed_name"], r["domain"],
                        r["content_type"], r["status"],
                        f"{(r['confidence'] or 0):.2f}", r["decision"], context, "", ""])
    return str(out)


def write_html(con, folder_symptoms: dict = None, out_path: Optional[str] = None) -> str:
    folder_symptoms = folder_symptoms or {}
    out = Path(out_path or (config.REPORTS_DIR / "rename_plan.html"))
    c = db.counts(con)
    rows = db.all_proposed(con)

    sym_lookup = {s["id"]: s for s in config.SYMPTOM_REGISTRY}

    def esc(x):
        return html.escape(str(x if x is not None else ""))

    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<title>FIS Rename Plan</title><style>
body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:2rem;color:#1a1a1a}}
h1{{margin:0 0 .25rem}} .sub{{color:#666;margin-bottom:1.5rem}}
.cards{{display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap}}
.card{{background:#f5f5f7;border-radius:10px;padding:.8rem 1.2rem;min-width:120px}}
.card b{{font-size:1.6rem;display:block}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #eee;vertical-align:top}}
th{{background:#fafafa;position:sticky;top:0}}
code{{background:#f0f0f3;padding:1px 5px;border-radius:4px}}
.q{{color:#b26a00}} .a{{color:#1a7f37}} .s{{color:#999}}
.sym{{display:inline-block;background:#fff3e0;border:1px solid #ffcc80;border-radius:4px;
padding:0 5px;margin:1px;font-size:11px}}
</style></head><body>
<h1>FIS Rename Plan</h1>
<div class="sub">Propose-only. Nothing has been renamed. Generated {esc(datetime.now().strftime('%Y-%m-%d %H:%M'))}.</div>
<div class="cards">
  <div class="card"><b>{c['total']}</b>files scanned</div>
  <div class="card"><b>{len(rows)}</b>names proposed</div>
  <div class="card"><b>{c['pending']}</b>pending review</div>
  <div class="card"><b>{c['auto_approve']}</b>auto-approve</div>
  <div class="card"><b>{c['skip']}</b>skipped</div>
</div>"""]

    if folder_symptoms:
        parts.append("<h2>Folder symptoms</h2><table><tr><th>Folder</th><th>Symptoms</th></tr>")
        for folder, syms in sorted(folder_symptoms.items()):
            chips = " ".join(
                f'<span class="sym" title="{esc(sym_lookup.get(s,{}).get("name",""))}">{esc(s)} '
                f'{esc(sym_lookup.get(s,{}).get("name",""))}</span>' for s in syms)
            parts.append(f"<tr><td><code>{esc(folder)}</code></td><td>{chips}</td></tr>")
        parts.append("</table>")

    parts.append("<h2>Proposed names</h2><table>"
                 "<tr><th>#</th><th>Current</th><th>Proposed</th><th>Domain</th>"
                 "<th>Type</th><th>Conf</th><th>Decision</th></tr>")
    cls = {"queue": "q", "auto_approve": "a", "skip": "s"}
    for i, r in enumerate(rows, 1):
        d = r["decision"] or ""
        parts.append(
            f"<tr><td>{i}</td><td>{esc(r['name'])}</td>"
            f"<td><code>{esc(r['proposed_name'])}</code></td>"
            f"<td>{esc(r['domain'])}</td><td>{esc(r['content_type'])}</td>"
            f"<td>{(r['confidence'] or 0):.2f}</td>"
            f"<td class='{cls.get(d,'')}'>{esc(d)}</td></tr>")
    parts.append("</table></body></html>")

    out.write_text("\n".join(parts), encoding="utf-8")
    return str(out)


def build_all(folder_symptoms: dict = None, db_path: str = None) -> dict:
    con = db.connect(db_path)
    try:
        csv_path = write_csv(con)
        html_path = write_html(con, folder_symptoms)
        return {"csv": csv_path, "html": html_path}
    finally:
        con.close()
