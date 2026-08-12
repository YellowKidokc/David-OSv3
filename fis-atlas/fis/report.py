# fis-op: gov
"""Layered report render (spec): Layer 1 answer · Layer 2 explanation · Layer 3 receipts.

Renders the report_model into the gold-on-black house style. Dependency-free.
Quarto/Typst/WeasyPrint are FUTURE render adapters over the same report_model.json;
this keeps the pipeline runnable today with zero installs.
"""
from __future__ import annotations

import html

SEV_COLOR = {"critical": "#e0574a", "high": "#e0913a", "medium": "#d8c24a", "low": "#6f9e6a"}


def render_report(model: dict, root: str) -> str:
    findings = model["findings"]
    questions = model["open_questions"]
    top = sorted(findings, key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}
                 .get(f["severity"], 9))[:3]

    def fcard(f):
        c = SEV_COLOR.get(f["severity"], "#888")
        return f"""<div class="find" style="border-left-color:{c}">
          <div class="claim">{html.escape(f['claim'])}</div>
          <div class="grid">
            <div><b>Evidence</b><span class="dim">{len(f['evidence_ids'])} observations</span></div>
            <div><b>Interpretation</b>{html.escape(f['interpretation'])}</div>
            <div><b>Consequence</b>{html.escape(f['consequence'])}</div>
            <div><b>Action</b>{html.escape(f['recommended_action'])}</div>
          </div>
          <div class="meta">{f['severity']} · confidence {f['confidence']:.2f}
            {('· ' + html.escape(f['automation_effect'])) if f.get('automation_effect') else ''}</div>
        </div>"""

    def qcard(q):
        opts = "".join(f"<li>{html.escape(o)}</li>" for o in q["options"])
        blk = "🔒 blocks action" if q["blocking"] else "non-blocking"
        return f"""<div class="q">
          <div class="qh">{html.escape(q['question'])}</div>
          <ul>{opts}</ul>
          <div class="meta">{blk} · scope {q['ruling_scope']} · affects {q['affected_count']} objects
             · priority {q['priority']} · would affect: {', '.join(q['blocking_actions'])}</div>
        </div>"""

    s = model["scope"]
    return f"""<!doctype html><meta charset="utf-8"><title>FIS Report — {html.escape(root)}</title>
<style>
:root{{--bg:#0a0a0a;--panel:#121110;--line:#242220;--ink:#ececec;--mut:#8f8a83;--dim:#5c5852;--gold:#e0b34a;
--serif:Georgia,serif;--mono:ui-monospace,Consolas,monospace}}
body{{margin:0;background:radial-gradient(1000px 400px at 50% -80px,rgba(224,179,74,.06),transparent),var(--bg);
color:var(--ink);font-family:var(--mono);font-size:13px;padding:24px 30px 80px;max-width:1000px;margin:auto}}
h1{{font-family:var(--serif);font-size:34px;margin:0}} h1 .g{{color:var(--gold);font-style:italic}}
h2{{font-family:var(--serif);font-size:22px;margin:30px 0 6px;border-bottom:1px solid var(--line);padding-bottom:5px}}
.layer{{color:var(--dim);letter-spacing:2px;font-size:10px;text-transform:uppercase;margin-top:26px}}
.find{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);
border-radius:8px;padding:14px 16px;margin:10px 0}}
.claim{{font-weight:700;font-size:14px;margin-bottom:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px 18px;font-size:12px}}
.grid b{{color:var(--gold);display:block;font-size:10px;text-transform:uppercase;letter-spacing:1px}}
.grid span{{color:var(--dim)}} .meta{{color:var(--dim);font-size:11px;margin-top:8px}} .dim{{color:var(--dim)}}
.q{{background:var(--panel);border:1px solid #3a2f16;border-radius:8px;padding:14px 16px;margin:10px 0}}
.qh{{font-weight:700;color:var(--gold)}} .q ul{{margin:8px 0}} .q li{{color:var(--mut);margin:3px 0}}
.tiles{{display:flex;gap:12px;margin:14px 0}}
.tile{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 16px}}
.tile .n{{font-size:20px;font-weight:700}} .tile .l{{font-size:11px;color:var(--dim)}}
</style>
<h1>Corpus <span class="g">report.</span></h1>
<div class="dim">{html.escape(root)} · report-only · nothing executed · audience: {model['audience']}</div>
<div class="tiles">
  <div class="tile"><div class="n">{s['files']:,}</div><div class="l">files</div></div>
  <div class="tile"><div class="n">{s['folders']:,}</div><div class="l">folders</div></div>
  <div class="tile"><div class="n">{s['bytes']/1e9:.2f} GB</div><div class="l">size</div></div>
  <div class="tile"><div class="n">{len(findings)}</div><div class="l">findings</div></div>
  <div class="tile"><div class="n">{len(questions)}</div><div class="l">open questions</div></div>
</div>

<div class="layer">Layer 1 — the answer (read this first)</div>
<h2>Executive summary</h2>
{''.join(fcard(f) for f in top)}

<div class="layer">Layer 2 — the explanation</div>
<h2>All findings — claim · evidence · interpretation · consequence · action</h2>
{''.join(fcard(f) for f in findings)}

<h2>Questions that need a human ruling</h2>
{''.join(qcard(q) for q in questions) or '<p class="dim">No blocking questions.</p>'}

<div class="layer">Layer 3 — the receipts</div>
<h2>Report model</h2>
<p class="dim">Every sentence above traces to this structured model
({len(findings)} findings, {len(questions)} questions). Exported as
<b>report_model.json</b> — the object a Quarto/Typst renderer would consume next.</p>
"""
