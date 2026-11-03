#!/usr/bin/env python3
"""Generate a Theophysics Corpus Audit Report from chi_catalog_v2.db."""
import sqlite3, datetime
from pathlib import Path

DB = r"D:\DONT TOUCH BOOT UP\filetagger\chi_catalog_v2.db"
OUT = r"D:\DONT TOUCH BOOT UP\filetagger\corpus_audit.html"

db = sqlite3.connect(DB)
total = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# Gather data
chi_dist = db.execute(
    "SELECT chi_primary, COUNT(*), ROUND(AVG(chi_confidence),1) "
    "FROM files WHERE chi_primary IS NOT NULL AND chi_primary != 'UC' "
    "GROUP BY chi_primary ORDER BY COUNT(*) DESC").fetchall()

domain_dist = db.execute(
    "SELECT domain_primary, COUNT(*) FROM files WHERE domain_primary != '' "
    "GROUP BY domain_primary ORDER BY COUNT(*) DESC LIMIT 15").fetchall()

law_dist = db.execute(
    "SELECT law_primary, COUNT(*) FROM files WHERE law_primary != '' "
    "GROUP BY law_primary ORDER BY COUNT(*) DESC").fetchall()

type_dist = db.execute(
    "SELECT content_type, COUNT(*) FROM files "
    "GROUP BY content_type ORDER BY COUNT(*) DESC").fetchall()

ext_dist = db.execute(
    "SELECT ext, COUNT(*) FROM files GROUP BY ext ORDER BY COUNT(*) DESC LIMIT 15").fetchall()

high_evidence = db.execute(
    "SELECT name, evidence, chi_primary, domain_primary, law_primary FROM files "
    "WHERE evidence > 0 ORDER BY evidence DESC LIMIT 20").fetchall()

high_fruit = db.execute(
    "SELECT name, fruit, chi_primary, domain_primary FROM files "
    "WHERE fruit > 0 ORDER BY fruit DESC LIMIT 15").fetchall()

high_anti = db.execute(
    "SELECT name, anti_fruit, chi_primary, domain_primary FROM files "
    "WHERE anti_fruit > 0 ORDER BY anti_fruit DESC LIMIT 15").fetchall()

unclassified = db.execute(
    "SELECT COUNT(*) FROM files WHERE chi_primary = 'UC' OR chi_primary IS NULL"
).fetchone()[0]

def bar(val, mx, color="#d4af37"):
    pct = min(100, (val / max(mx, 1)) * 100)
    return f'<div style="background:{color};height:18px;width:{pct}%;border-radius:3px;min-width:2px"></div>'

def row(label, count, mx, extra="", color="#d4af37"):
    return f"""<tr>
        <td style="font-family:monospace;font-weight:600;width:200px">{label}</td>
        <td style="text-align:right;width:80px;color:#d4af37">{count:,}</td>
        <td style="width:300px;padding:4px 8px">{bar(count, mx, color)}</td>
        <td style="color:#9a9a9a;font-size:12px">{extra}</td>
    </tr>"""

chi_names = {
    'G':'Grace','M':'Moral Alignment','E':'Truth Signal','S':'Entropy/Judgment',
    'T':'Time/Kairos','K':'Knowledge/Info','R':'Relational','Q':'Quantum/Faith',
    'F':'Moral Force','C':'Coherence/Christ','CHI':'Master Equation','UC':'Unclassified'
}

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Theophysics Corpus Audit Report</title>
<style>
:root{{--bg:#050505;--surface:#0a0a0a;--surface2:#111;--border:#222;
--text:#e5e3df;--text-dim:#9a9a9a;--gold:#d4af37;--green:#4ade80;
--amber:#fb923c;--red:#f87171;--blue:#38bdf8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);
color:var(--text);line-height:1.5;padding:24px}}
.container{{max-width:1100px;margin:0 auto}}
h1{{font-family:'Oswald',sans-serif;font-size:28px;color:var(--gold);
border-bottom:2px solid var(--gold);padding-bottom:12px;margin-bottom:24px}}
h2{{font-size:16px;color:var(--gold);margin:32px 0 12px;
text-transform:uppercase;letter-spacing:1px}}
.card{{background:var(--surface);border:1px solid var(--border);
border-radius:8px;padding:20px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse}}
td{{padding:6px 8px;border-bottom:1px solid #1a1a1a;vertical-align:middle}}
.stat{{display:inline-block;text-align:center;padding:12px 24px;
background:var(--surface2);border-radius:8px;margin:4px}}
.stat .num{{font-size:32px;font-weight:700;color:var(--gold)}}
.stat .label{{font-size:11px;color:var(--text-dim);text-transform:uppercase}}
.gap{{border-left:3px solid var(--red);padding-left:12px;margin:8px 0;
color:var(--text-dim);font-size:13px}}
.strong{{border-left:3px solid var(--green);padding-left:12px;margin:8px 0;
color:var(--text-dim);font-size:13px}}
</style></head>
<body><div class="container">
"""

html += f"""
<h1>THEOPHYSICS CORPUS AUDIT REPORT</h1>
<div style="color:var(--text-dim);margin-bottom:24px;font-size:13px">
Generated: {now} | Engine: filetagger_chi_v2.py | POF 2828
</div>

<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px">
<div class="stat"><div class="num">{total:,}</div><div class="label">Total Files</div></div>
<div class="stat"><div class="num">{total - unclassified:,}</div><div class="label">Classified</div></div>
<div class="stat"><div class="num">{unclassified:,}</div><div class="label">Unclassified</div></div>
<div class="stat"><div class="num">{round((total-unclassified)/total*100,1)}%</div><div class="label">Coverage</div></div>
</div>
"""

# Chi Factors
chi_max = chi_dist[0][1] if chi_dist else 1
html += '<h2>Chi Factor Distribution (Master Equation)</h2><div class="card"><table>'
for factor, count, conf in chi_dist:
    name = chi_names.get(factor, factor)
    html += row(f"[{factor}] {name}", count, chi_max, f"avg {conf}%")
html += '</table></div>'

# Gaps
html += '<h2>Gap Analysis</h2><div class="card">'
chi_dict = {f: c for f, c, _ in chi_dist}
gaps = sorted(chi_dict.items(), key=lambda x: x[1])[:3]
strengths = sorted(chi_dict.items(), key=lambda x: -x[1])[:3]
for f, c in gaps:
    html += f'<div class="gap"><strong>[{f}] {chi_names.get(f,f)}</strong> - {c:,} files. This factor is underrepresented in the corpus.</div>'
for f, c in strengths:
    html += f'<div class="strong"><strong>[{f}] {chi_names.get(f,f)}</strong> - {c:,} files. Strong coverage.</div>'
html += '</div>'

# Domains
dom_max = domain_dist[0][1] if domain_dist else 1
html += '<h2>Domain Distribution</h2><div class="card"><table>'
for dom, count in domain_dist:
    html += row(dom, count, dom_max, color="#38bdf8")
html += '</table></div>'

# Laws
law_max = law_dist[0][1] if law_dist else 1
html += '<h2>Ten Laws Coverage</h2><div class="card"><table>'
for law, count in law_dist:
    html += row(law, count, law_max, color="#4ade80")
html += '</table></div>'

# Law gaps
html += '<div class="card">'
law_dict = {l: c for l, c in law_dist}
all_laws = ["L01_Gravity_Grace","L02_Motion_Will","L03_EM_Truth",
    "L04_Strong_Love","L05_Thermo_Justice","L06_Info_Logos",
    "L07_Quantum_Faith","L08_Relativity_Grace","L09_Weak_Conservation",
    "L10_Coherence_Christ"]
for law in all_laws:
    c = law_dict.get(law, 0)
    if c < 100:
        html += f'<div class="gap"><strong>{law}</strong> - only {c} files. Needs attention.</div>'
html += '</div>'

# Content types
type_max = type_dist[0][1] if type_dist else 1
html += '<h2>Content Types</h2><div class="card"><table>'
for ct, count in type_dist:
    html += row(ct, count, type_max, color="#fb923c")
html += '</table></div>'

# Extensions
html += '<h2>File Extensions</h2><div class="card"><table>'
ext_max = ext_dist[0][1] if ext_dist else 1
for ext, count in ext_dist:
    html += row(ext or "[none]", count, ext_max, color="#9a9a9a")
html += '</table></div>'

# High evidence files
html += '<h2>Highest Evidence Density</h2><div class="card"><table>'
html += '<tr><td style="color:var(--text-dim)">Score</td><td style="color:var(--text-dim)">Chi</td><td style="color:var(--text-dim)">Domain</td><td style="color:var(--text-dim)">File</td></tr>'
for name, ev, chi, dom, law in high_evidence[:15]:
    html += f'<tr><td style="color:var(--gold)">{ev}%</td><td>[{chi}]</td><td>{dom}</td><td style="font-size:12px">{name[:60]}</td></tr>'
html += '</table></div>'

# Fruit / anti-fruit
html += '<h2>Fruit Presence (top files)</h2><div class="card"><table>'
for name, fr, chi, dom in high_fruit[:10]:
    html += f'<tr><td style="color:var(--green)">{fr}%</td><td>[{chi}]</td><td>{dom}</td><td style="font-size:12px">{name[:60]}</td></tr>'
html += '</table></div>'

html += '<h2>Anti-Fruit Presence (watch list)</h2><div class="card"><table>'
for name, af, chi, dom in high_anti[:10]:
    html += f'<tr><td style="color:var(--red)">{af}%</td><td>[{chi}]</td><td>{dom}</td><td style="font-size:12px">{name[:60]}</td></tr>'
html += '</table></div>'

# Close
html += f"""
<h2>Methodology</h2>
<div class="card" style="font-size:13px;color:var(--text-dim)">
<p>This report was generated by filetagger_chi_v2.py using keyword classification
against the Master Equation vocabulary (10 chi factors, 10 domains, 10 Laws).
Classification is based on sampled text (first 4KB for text files, first 2 pages
for PDFs). Confidence scores reflect keyword density, not semantic understanding.</p>
<p style="margin-top:8px">Files with evidence density or fruit/anti-fruit scores
above threshold are candidates for deep analysis via
chi_jm_diagnostic_engine_v4_gold.py.</p>
</div>

</div></body></html>"""

Path(OUT).write_text(html, encoding="utf-8")
print(f"Audit report: {OUT}")
db.close()
