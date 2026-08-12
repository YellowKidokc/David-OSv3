# fis-op: gov
"""Render the atlas as a gold-on-black HTML page (David's end style).
Self-contained, no external assets. Preview-only view.
"""
from __future__ import annotations

import html
from .model import Atlas

RISK_ICON = {"red": "🔴", "amber": "🟡", "green": "🟢"}


def render_html(atlas: Atlas) -> str:
    o = atlas
    n_obj, n_fold = len(o.objects), len(o.folders)
    reclaim = sum(atlas.objects[m].size for c in o.clusters if c.kind == "duplicates" for m in c.members) // 2

    cluster_cards = "\n".join(
        f'<div class="cl"><div class="cl-h">{html.escape(c.label)}</div>'
        f'<div class="cl-r">{html.escape(c.proposed_rule or "—")}</div></div>'
        for c in o.clusters
    )

    rows = []
    for ob in sorted(o.objects.values(), key=lambda x: (x.risk != "red", x.rel_path.lower())):
        rows.append(
            f"<tr class='{ob.risk}'>"
            f"<td>{html.escape(ob.name)}</td>"
            f"<td class='dim'>{html.escape(ob.rel_path)}</td>"
            f"<td>{ob.content_type}</td><td>{ob.detected_role}</td>"
            f"<td>{ob.sensitivity}</td>"
            f"<td class='r-{ob.risk}'>{RISK_ICON.get(ob.risk,'')} {ob.risk}</td>"
            f"<td>{ob.proposed_treatment}</td>"
            f"<td class='dim'>{ob.class_confidence:.2f}/{ob.action_confidence:.2f}</td>"
            f"</tr>"
        )
    table = "\n".join(rows)

    return f"""<!doctype html><meta charset="utf-8"><title>FIS Atlas — {html.escape(o.root)}</title>
<style>
:root{{--bg:#0a0a0a;--panel:#121110;--line:#242220;--ink:#ececec;--mut:#8f8a83;--dim:#5c5852;--gold:#e0b34a;
--crit:#e0574a;--med:#d8c24a;--low:#6f9e6a;--serif:Georgia,'Times New Roman',serif;
--mono:ui-monospace,Consolas,monospace;}}
body{{margin:0;background:radial-gradient(1000px 400px at 50% -80px,rgba(224,179,74,.06),transparent),var(--bg);
color:var(--ink);font-family:var(--mono);font-size:13px;padding:22px 26px 70px}}
h1{{font-family:var(--serif);font-weight:600;font-size:34px;margin:0 0 2px}}
h1 .g{{color:var(--gold);font-style:italic}} .mut{{color:var(--mut)}} .dim{{color:var(--dim)}}
.tiles{{display:flex;gap:12px;margin:16px 0}}
.tile{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px}}
.tile .n{{font-size:22px;font-weight:700}} .tile .l{{font-size:11px;color:var(--dim)}}
.tile .n.g{{color:var(--gold)}}
h2{{font-family:var(--serif);font-size:20px;margin:26px 0 8px}}
.cls{{display:flex;flex-wrap:wrap;gap:10px}}
.cl{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:200px}}
.cl-h{{font-weight:700}} .cl-r{{font-size:11px;color:var(--mut);margin-top:3px}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:12px}}
th{{text-align:left;color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:1px;
border-bottom:1px solid var(--line);padding:7px 9px}}
td{{padding:7px 9px;border-bottom:1px solid #1a1815}}
tr.red{{background:rgba(224,87,74,.06)}}
.r-red{{color:var(--crit);font-weight:700}} .r-amber{{color:var(--med)}} .r-green{{color:var(--low)}}
</style>
<h1>File-and-folder <span class="g">atlas.</span></h1>
<div class="mut">{html.escape(o.root)} · every object recorded · preview only, nothing executed</div>
<div class="tiles">
  <div class="tile"><div class="n">{n_obj}</div><div class="l">files</div></div>
  <div class="tile"><div class="n">{n_fold}</div><div class="l">folders</div></div>
  <div class="tile"><div class="n">{len(o.clusters)}</div><div class="l">clusters</div></div>
  <div class="tile"><div class="n g">{reclaim/1e6:.1f} MB</div><div class="l">dup reclaim</div></div>
</div>
<h2>Clusters — decide at the highest safe level</h2>
<div class="cls">{cluster_cards}</div>
<h2>Every object — what it is · what it belongs with · certainty · authorization</h2>
<table>
<thead><tr><th>Name</th><th>Path</th><th>Type</th><th>Role</th><th>Sensitivity</th>
<th>Risk</th><th>Treatment</th><th>Conf (class/act)</th></tr></thead>
<tbody>{table}</tbody></table>
"""
