"""
FOLDER SCAN REPORT GENERATOR
==============================
Generates a standalone HTML report from scan results.
Import this and call generate_report(report, output_path).

Or run standalone:
  python scan_report.py scan_results.json -o report.html
"""

import json
import sys
import datetime
from pathlib import Path


def generate_report(report_data: dict, output_path: str = None, previous_data: dict = None) -> str:
    """Generate HTML report from scan results dict. Returns HTML string."""

    target = report_data.get("target", "Unknown")
    target_name = Path(target).name or target
    scanned_at = report_data.get("scanned_at", "")
    total_files = report_data.get("total_files", 0)
    total_dirs = report_data.get("total_dirs", 0)
    grade = report_data.get("grade", "?")
    score = report_data.get("score", 0)
    symptoms = report_data.get("symptoms", [])

    # Grade color
    grade_colors = {"A": "#4ade80", "B": "#86efac", "C": "#fbbf24", "D": "#f97316", "F": "#ef4444", "?": "#6b7280"}
    grade_color = grade_colors.get(grade, "#6b7280")

    # Category counts
    cat_counts = {}
    for s in symptoms:
        cat = s.get("category", "Unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Severity counts
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for s in symptoms:
        sev = s.get("severity", "low")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    # Build work order (sorted by severity, then count)
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    work_items = sorted(symptoms, key=lambda s: (sev_order.get(s["severity"], 9), -s["count"]))

    # Comparison with previous scan
    delta_html = ""
    if previous_data:
        prev_score = previous_data.get("score", 0)
        prev_count = len(previous_data.get("symptoms", []))
        diff = score - prev_score
        arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
        delta_color = "#4ade80" if diff > 0 else "#ef4444" if diff < 0 else "#9aa1b0"
        delta_html = f"""
        <div class="delta-card">
            <span class="delta-arrow" style="color:{delta_color}">{arrow} {abs(diff):.0f} pts</span>
            <span class="delta-label">vs previous scan</span>
            <span class="delta-detail">Was: {prev_score:.0f}/100 ({prev_count} symptoms) → Now: {score:.0f}/100 ({len(symptoms)} symptoms)</span>
        </div>"""

    # Build symptom rows
    symptom_rows = ""
    for s in work_items:
        sev = s["severity"]
        sev_badge_colors = {"critical": "#dc2626", "high": "#ea580c", "medium": "#d97706", "low": "#6b7280"}
        badge_bg = sev_badge_colors.get(sev, "#6b7280")
        auto_tag = '<span class="auto-tag">AUTO-FIX</span>' if s.get("auto_fixable") else ""
        paths_html = ""
        for p in s.get("affected_paths", [])[:5]:
            paths_html += f'<div class="path-item">{_esc(p)}</div>'
        remaining = len(s.get("affected_paths", [])) - 5
        if remaining > 0:
            paths_html += f'<div class="path-more">... and {remaining} more</div>'

        symptom_rows += f"""
        <div class="symptom-card">
            <div class="symptom-header">
                <span class="symptom-id">{s["id"]}</span>
                <span class="sev-badge" style="background:{badge_bg}">{sev.upper()}</span>
                <span class="symptom-name">{_esc(s["name"])}</span>
                <span class="symptom-count">{s["count"]}</span>
                {auto_tag}
            </div>
            <div class="symptom-desc">{_esc(s.get("description", ""))}</div>
            <div class="paths-list">{paths_html}</div>
        </div>"""

    # Work order section
    work_order_rows = ""
    priority = 1
    for s in work_items:
        if s["count"] == 0:
            continue
        effort = "5 min" if s.get("auto_fixable") else {"low": "15 min", "medium": "30 min", "high": "1 hr", "critical": "ASAP"}[s["severity"]]
        action = _get_recommended_action(s["id"])
        work_order_rows += f"""
        <tr>
            <td class="wo-pri">{priority}</td>
            <td><span class="sev-badge-sm" style="background:{sev_badge_colors.get(s['severity'], '#6b7280')}">{s['severity'][0].upper()}</span></td>
            <td class="wo-id">{s["id"]}</td>
            <td>{_esc(s["name"])}</td>
            <td class="wo-count">{s["count"]}</td>
            <td class="wo-action">{action}</td>
            <td class="wo-effort">{effort}</td>
        </tr>"""
        priority += 1

    # Category breakdown bars
    cat_bars = ""
    max_cat = max(cat_counts.values()) if cat_counts else 1
    cat_colors = {"Structural": "#5fb3ae", "Content": "#d9a441", "Temporal": "#8b5cf6",
                  "Infrastructure": "#ef4444", "Naming": "#6366f1", "Research Corpus": "#22c55e"}
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        pct = (count / max_cat) * 100
        color = cat_colors.get(cat, "#9aa1b0")
        cat_bars += f"""
        <div class="cat-row">
            <span class="cat-label">{cat}</span>
            <div class="cat-bar-bg"><div class="cat-bar-fill" style="width:{pct}%;background:{color}"></div></div>
            <span class="cat-count">{count}</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scan Report — {_esc(target_name)}</title>
<style>
:root {{
    --bg: #0f1117;
    --panel: #161922;
    --panel-2: #1c2030;
    --line: #262d3d;
    --amber: #d9a441;
    --cyan: #5fb3ae;
    --ink: #e4e1d8;
    --ink-dim: #8f96a3;
    --ink-faint: #555d6e;
    --red: #ef4444;
    --green: #4ade80;
    --radius: 8px;
}}
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap');
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--ink); font-family: 'Inter', sans-serif; font-size: 14px; line-height: 1.6; padding: 24px; max-width: 1100px; margin: 0 auto; }}
h1 {{ font-family: 'Space Grotesk', sans-serif; font-size: 22px; font-weight: 600; color: var(--amber); margin-bottom: 4px; }}
h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; color: var(--ink-faint); margin: 32px 0 16px 0; display: flex; align-items: center; gap: 8px; }}
h2::before {{ content: ''; width: 4px; height: 4px; background: var(--amber); border-radius: 50%; }}
.subtitle {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-dim); margin-bottom: 24px; }}

/* Grade */
.grade-section {{ display: flex; align-items: center; gap: 24px; padding: 24px; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); margin-bottom: 20px; flex-wrap: wrap; }}
.grade-circle {{ width: 80px; height: 80px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-family: 'Space Grotesk', sans-serif; font-size: 36px; font-weight: 700; color: #0f1117; flex-shrink: 0; }}
.grade-info {{ flex: 1; min-width: 200px; }}
.grade-score {{ font-family: 'Space Grotesk', sans-serif; font-size: 18px; font-weight: 600; }}
.grade-meta {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-dim); margin-top: 4px; }}
.stats-row {{ display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap; }}
.stat {{ background: var(--panel-2); padding: 8px 14px; border-radius: 6px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; }}
.stat b {{ color: var(--amber); }}

/* Delta */
.delta-card {{ background: var(--panel-2); border: 1px solid var(--line); border-radius: var(--radius); padding: 12px 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
.delta-arrow {{ font-family: 'Space Grotesk', sans-serif; font-size: 20px; font-weight: 700; }}
.delta-label {{ font-size: 13px; color: var(--ink-dim); }}
.delta-detail {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--ink-faint); margin-left: auto; }}

/* Severity summary */
.sev-row {{ display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
.sev-chip {{ padding: 6px 14px; border-radius: 20px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 500; }}

/* Category bars */
.cat-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
.cat-label {{ width: 130px; font-size: 12px; color: var(--ink-dim); text-align: right; flex-shrink: 0; }}
.cat-bar-bg {{ flex: 1; height: 14px; background: var(--panel-2); border-radius: 7px; overflow: hidden; }}
.cat-bar-fill {{ height: 100%; border-radius: 7px; transition: width 0.5s; }}
.cat-count {{ width: 30px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-dim); }}

/* Symptoms */
.symptom-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 18px; margin-bottom: 10px; }}
.symptom-header {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.symptom-id {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--cyan); font-weight: 500; }}
.sev-badge {{ font-size: 10px; font-weight: 600; color: #fff; padding: 2px 8px; border-radius: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
.sev-badge-sm {{ font-size: 9px; font-weight: 600; color: #fff; padding: 1px 6px; border-radius: 8px; }}
.symptom-name {{ font-weight: 600; font-size: 14px; }}
.symptom-count {{ margin-left: auto; font-family: 'IBM Plex Mono', monospace; font-size: 13px; color: var(--amber); font-weight: 600; }}
.auto-tag {{ font-size: 9px; font-weight: 600; color: var(--green); border: 1px solid var(--green); padding: 1px 6px; border-radius: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
.symptom-desc {{ font-size: 12.5px; color: var(--ink-dim); margin-top: 6px; }}
.paths-list {{ margin-top: 8px; }}
.path-item {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--ink-faint); padding: 2px 0; word-break: break-all; }}
.path-more {{ font-size: 11px; color: var(--ink-faint); font-style: italic; }}

/* Work order table */
.wo-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.wo-table th {{ font-family: 'Space Grotesk', sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--ink-faint); text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
.wo-table td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); }}
.wo-pri {{ font-family: 'IBM Plex Mono', monospace; color: var(--amber); font-weight: 600; }}
.wo-id {{ font-family: 'IBM Plex Mono', monospace; color: var(--cyan); }}
.wo-count {{ font-family: 'IBM Plex Mono', monospace; text-align: center; }}
.wo-action {{ font-size: 12px; color: var(--ink-dim); }}
.wo-effort {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--ink-faint); white-space: nowrap; }}

/* Footer */
.footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--line); font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--ink-faint); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}

/* Clean section */
.clean-banner {{ background: linear-gradient(135deg, #064e3b, #0f1117); border: 1px solid #22c55e33; border-radius: var(--radius); padding: 24px; text-align: center; }}
.clean-banner h3 {{ font-family: 'Space Grotesk', sans-serif; font-size: 20px; color: var(--green); margin-bottom: 8px; }}

@media print {{ body {{ background: #fff; color: #111; }} .grade-circle {{ border: 3px solid #000; }} }}
</style>
</head>
<body>

<h1>Folder Health Report</h1>
<div class="subtitle">{_esc(target)} — {scanned_at[:19] if scanned_at else "unknown"}</div>

<div class="grade-section">
    <div class="grade-circle" style="background:{grade_color}">{grade}</div>
    <div class="grade-info">
        <div class="grade-score">{score:.0f} / 100</div>
        <div class="grade-meta">{total_files:,} files across {total_dirs:,} directories</div>
        <div class="stats-row">
            <div class="stat"><b>{sev_counts["critical"]}</b> critical</div>
            <div class="stat"><b>{sev_counts["high"]}</b> high</div>
            <div class="stat"><b>{sev_counts["medium"]}</b> medium</div>
            <div class="stat"><b>{sev_counts["low"]}</b> low</div>
            <div class="stat"><b>{len(symptoms)}</b> total symptoms</div>
        </div>
    </div>
</div>

{delta_html}

<div class="sev-row">
    <span class="sev-chip" style="background:#dc262633;color:#fca5a5">⚠ {sev_counts["critical"]} Critical</span>
    <span class="sev-chip" style="background:#ea580c33;color:#fdba74">▲ {sev_counts["high"]} High</span>
    <span class="sev-chip" style="background:#d9770633;color:#fde68a">▪ {sev_counts["medium"]} Medium</span>
    <span class="sev-chip" style="background:#6b728033;color:#d1d5db">· {sev_counts["low"]} Low</span>
</div>

<h2>Category Breakdown</h2>
{cat_bars}

{"" if symptoms else '<div class="clean-banner"><h3>✓ No symptoms detected</h3><p>This folder is clean.</p></div>'}

{"<h2>Work Order</h2>" if work_order_rows else ""}
{"<table class='wo-table'><thead><tr><th>#</th><th>Sev</th><th>ID</th><th>Symptom</th><th>Count</th><th>Action</th><th>Effort</th></tr></thead><tbody>" + work_order_rows + "</tbody></table>" if work_order_rows else ""}

<h2>Symptom Details</h2>
{symptom_rows if symptom_rows else '<div style="color:var(--ink-faint)">No symptoms to display.</div>'}

<div class="footer">
    <span>Folder Symptom Scanner v1.0 — Source 22003</span>
    <span>Schema: TopOfMind v1.0</span>
    <span>Generated {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
</div>

</body>
</html>"""

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")

    return html


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _get_recommended_action(symptom_id: str) -> str:
    actions = {
        "S01": "Split files by content family into subfolders",
        "S02": "Diff versions → keep latest → archive old",
        "S03": "Flatten nested paths, preserve in .chi metadata",
        "S04": "Classify by domain/date into subfolders",
        "S05": "Link orphan sidecars to parents or quarantine",
        "S06": "Hash compare → rename to disambiguate",
        "S07": "Build project manifest → consolidate",
        "S08": "Report broken refs → suggest replacement targets",
        "C01": "Hash compare → review keeper → archive duplicates",
        "C02": "Pick canonical format → archive redundant copies",
        "C03": "Extract insights from drafts → archive raw",
        "C04": "Sort mixed docs by topic + project + date",
        "C05": "Rename by EXIF date/source → sort into folders",
        "C06": "Quarantine unknown files → manual review",
        "C07": "Normalize all text files to UTF-8",
        "C08": "Verify extraction complete → remove archive",
        "T01": "Flag stale files for archive review",
        "T02": "Group burst files by session → classify",
        "T03": "Identify final outputs → purge intermediates",
        "T04": "Snapshot state → archive or explicitly revive",
        "I01": "PROTECT — never auto-move or rename",
        "I02": "Clean orphaned build artifacts",
        "I03": "ALERT — secure exposed credentials immediately",
        "I04": "Diff sync conflicts → resolve → delete losers",
        "I05": "Separate untracked personal files from repos",
        "I06": "Hash compare local vs NAS → reconcile",
        "I07": "Delete broken shortcuts → rebuild valid ones",
        "I08": "Rotate logs → compress → archive old",
        "N01": "Suggest content-based renames",
        "N02": "Separate installers from documents",
        "N03": "Review empty folders → delete",
        "N04": "Shorten folder names or flatten structure",
        "R01": "Priority classify → generate .chi sidecar",
        "R02": "Extract insights from AI exports → archive raw",
        "R03": "Separate personal files from research dirs",
        "R04": "Tag files with source AI + date",
        "R05": "Move archives to dedicated backup folder",
        "R06": "Re-scan low-confidence files with more context",
        "R07": "Identify and fill content gaps by Law",
        "R08": "Flag for citation pass or deep engine review",
    }
    return actions.get(symptom_id, "Review and address manually")


# ── CLI ─────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scan_report.py scan_results.json [-o report.html] [--prev previous.json]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = "scan_report.html"
    prev_path = None

    for i, arg in enumerate(sys.argv):
        if arg == "-o" and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
        if arg == "--prev" and i + 1 < len(sys.argv):
            prev_path = sys.argv[i + 1]

    with open(input_path) as f:
        data = json.load(f)

    prev_data = None
    if prev_path:
        with open(prev_path) as f:
            prev_data = json.load(f)

    generate_report(data, output_path, prev_data)
    print(f"Report generated: {output_path}")
