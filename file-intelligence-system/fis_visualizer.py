"""
FIS 3D cluster map.

Reads the folder-memory registry, places every scored file in the shared vector
space (see fis_vector_space.py), clusters the result, and writes one
self-contained HTML page:

    reports/FIS_CLUSTER_MAP.html

No server, no CDN, no runtime dependencies - plotly.js is inlined into the page.
Clicking a dot opens the file's block in its own folder's FIS.html, so the map
is a view onto the folder web rather than a separate artefact.

    python fis_visualizer.py
    python fis_visualizer.py --path-prefix "D:\\01_Axioms" --cluster kmeans -k 8
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from collections import Counter
from pathlib import Path

from fis_vector_space import (DB_DEFAULT, DOC_TYPE_COLORS, MEQ_VARIABLE_NAMES,
                              load_points)

REPORTS = Path(__file__).with_name("reports")
OUT     = REPORTS / "FIS_CLUSTER_MAP.html"


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_points(points: list[dict], method: str = "dbscan", k: int = 8,
                   eps: float = 0.28, min_samples: int = 4) -> dict:
    """
    Attach a cluster id to every point. Returns a short report on the run.

    DBSCAN is the default because the corpus has no reason to contain a fixed
    number of groups, and its noise label (-1) is informative: those are the
    files that sit apart from every cluster.
    """
    if not points:
        return {"method": "none", "clusters": 0, "noise": 0}

    try:
        import numpy as np
        from sklearn.cluster import DBSCAN, KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        for p in points:
            p["cluster"] = -2          # -2 = clustering unavailable
        return {"method": "unavailable", "clusters": 0, "noise": 0,
                "note": "scikit-learn not installed; points placed but not clustered"}

    coords = np.array([[p["x"], p["y"], p["z"]] for p in points], dtype=float)
    scaled = StandardScaler().fit_transform(coords)

    if method == "kmeans":
        k = max(2, min(int(k), len(points)))
        labels = KMeans(n_clusters=k, n_init=10, random_state=2828).fit_predict(scaled)
    else:
        labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(scaled)

    for p, lab in zip(points, labels):
        p["cluster"] = int(lab)

    uniq  = {int(l) for l in labels}
    noise = sum(1 for l in labels if l == -1)
    return {"method": method, "clusters": len(uniq - {-1}), "noise": noise}


def cluster_profiles(points: list[dict]) -> list[dict]:
    """Describe each cluster by what it actually contains, not by its number."""
    by: dict[int, list[dict]] = {}
    for p in points:
        by.setdefault(p.get("cluster", -2), []).append(p)

    profiles = []
    for cid, members in sorted(by.items(), key=lambda kv: -len(kv[1])):
        types = Counter(m["doc_type"] for m in members)
        chis  = Counter(m["top_chi"] for m in members)
        doms  = Counter(m["domain"] for m in members)
        profiles.append({
            "cluster":   cid,
            "count":     len(members),
            "top_types": types.most_common(3),
            "top_chi":   chis.most_common(2),
            "top_domain": doms.most_common(2),
            "mean_coherence": round(sum(m["z"] for m in members) / len(members), 3),
            "mean_confidence": round(sum(m["confidence"] for m in members) / len(members), 3),
        })
    return profiles


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def _plotly_js() -> str:
    """Inline plotly.js so the page needs nothing at runtime."""
    try:
        from plotly.offline import get_plotlyjs
        return get_plotlyjs()
    except ImportError as exc:
        raise SystemExit("plotly is required to build the cluster map: pip install plotly") from exc


PAGE_CSS = """
:root{color-scheme:dark;--bg:#0b0d10;--panel:#12161d;--line:#303946;
      --text:#e7edf5;--muted:#94a3b8;--accent:#d1a922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
     font:14px/1.55 ui-sans-serif,system-ui,"Segoe UI",sans-serif}
header{padding:14px 18px;border-bottom:1px solid var(--line);background:var(--panel);
       display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
h1{margin:0;font-size:17px;letter-spacing:.4px}
h1 span{color:var(--accent)}
.meta{color:var(--muted);font-size:12px}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:0;
      height:calc(100vh - 56px)}
#plot{min-height:400px}
aside{border-left:1px solid var(--line);background:var(--panel);overflow-y:auto;padding:14px}
aside h2{font-size:12px;text-transform:uppercase;letter-spacing:1px;
         color:var(--muted);margin:0 0 8px}
.card{border:1px solid var(--line);background:#0d1117;padding:10px;margin:0 0 12px}
.card .fname{font-weight:600;word-break:break-word}
code{background:#0d1117;border:1px solid var(--line);padding:1px 5px;
     font-size:12px;word-break:break-all}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--muted);font-weight:500;width:96px;
   padding:3px 6px 3px 0;vertical-align:top}
td{padding:3px 0;word-break:break-word}
.pill{display:inline-block;padding:1px 7px;border-radius:2px;font-size:11px;
      font-weight:600;color:#0b0d10}
.note{white-space:pre-wrap;font-size:11.5px;color:var(--muted);max-height:230px;
      overflow:auto;border-top:1px solid var(--line);margin-top:8px;padding-top:8px}
a{color:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}
.legend span{font-size:11px;padding:1px 7px;border-radius:2px;color:#0b0d10;font-weight:600}
.muted{color:var(--muted)}
.bar{height:4px;background:#0d1117;border:1px solid var(--line);margin-top:3px}
.bar i{display:block;height:100%;background:var(--accent)}
"""

PAGE_JS = """
const POINTS = __POINTS__;
const byId = Object.fromEntries(POINTS.map(p => [p.file_id, p]));

function esc(s){ return String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function chiBars(chi){
  return Object.entries(chi).sort((a,b)=>b[1]-a[1]).filter(e=>e[1]>0)
    .map(([k,v])=>`<tr><th>${k} ${esc(MEQ[k]||'')}</th><td>${v}/3
       <div class="bar"><i style="width:${(v/3*100)}%"></i></div></td></tr>`).join('');
}

function show(p){
  const panel = document.getElementById('detail');
  if(!p){ panel.innerHTML = '<p class="muted">Click any dot to inspect the file.</p>'; return; }
  const link = p.page
    ? `<a href="${p.page}#${p.file_id}">open in folder page</a>`
    : '<span class="muted">no FIS.html for this folder yet</span>';
  panel.innerHTML = `
    <div class="card">
      <div class="fname">${esc(p.name)}</div>
      <div style="margin:6px 0"><span class="pill" style="background:${p.color}">${p.doc_type}</span>
        <span class="muted"> confidence ${p.confidence}</span></div>
      <table>
        <tr><th>Address</th><td><code>${esc(p.address||'-')}</code></td></tr>
        <tr><th>Domain</th><td>${esc(p.domain)} (${p.domain_score}/3)</td></tr>
        <tr><th>Top CHI</th><td>${esc(p.top_chi)} - ${esc(MEQ[p.top_chi]||'unclassified')}</td></tr>
        <tr><th>Law</th><td>${esc(p.law)}</td></tr>
        <tr><th>Coherence</th><td>${p.z}</td></tr>
        <tr><th>Cluster</th><td>${p.cluster === -1 ? 'outlier (no cluster)' : p.cluster}</td></tr>
        <tr><th>Path</th><td><code>${esc(p.path)}</code></td></tr>
        <tr><th>Open</th><td>${link}</td></tr>
      </table>
      <table style="margin-top:8px">${chiBars(p.chi)}</table>
      ${p.fisnote ? `<div class="note">${esc(p.fisnote)}</div>`
                  : '<div class="note muted">No .fisnote sidecar on disk for this file.</div>'}
    </div>`;
}

document.getElementById('plot').on('plotly_click', ev => {
  const id = ev.points[0].customdata && ev.points[0].customdata[0];
  if(id && byId[id]) show(byId[id]);
});
show(null);
"""


def build_page(points: list[dict], report: dict, profiles: list[dict],
               db_path: Path, out: Path) -> Path:
    import plotly.graph_objects as go

    traces = []
    for dtype in sorted({p["doc_type"] for p in points}):
        sel = [p for p in points if p["doc_type"] == dtype]
        traces.append(go.Scatter3d(
            x=[p["x"] for p in sel], y=[p["y"] for p in sel], z=[p["z"] for p in sel],
            mode="markers", name=f"{dtype} ({len(sel)})",
            customdata=[[p["file_id"]] for p in sel],
            marker=dict(
                size=[p["size"] for p in sel],
                color=DOC_TYPE_COLORS.get(dtype, "#4b5563"),
                opacity=0.85,
                line=dict(width=0.5, color="#0b0d10"),
            ),
            # Per-point opacity is not supported on Scatter3d markers, so
            # confidence is carried in the hover text and the panel instead of
            # being faked with a colour ramp that would read as a category.
            text=[f"<b>{p['name']}</b><br>{p['address']}<br>"
                  f"{p['doc_type']} · conf {p['confidence']}<br>"
                  f"domain {p['domain']} · top CHI {p['top_chi']}<br>"
                  f"coherence {p['z']}<br>{p['path']}" for p in sel],
            hoverinfo="text",
        ))

    fig = go.Figure(traces)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b0d10", plot_bgcolor="#0b0d10",
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(bgcolor="rgba(18,22,29,.85)", bordercolor="#303946", borderwidth=1,
                    font=dict(size=11)),
        scene=dict(
            xaxis=dict(title="theology ← domain → physics", range=[-1.05, 1.05],
                       gridcolor="#232a34", zerolinecolor="#3a4453", backgroundcolor="#0b0d10"),
            yaxis=dict(title="narrative ← document type → formal", range=[-1.05, 1.05],
                       gridcolor="#232a34", zerolinecolor="#3a4453", backgroundcolor="#0b0d10"),
            zaxis=dict(title="coherence / χ", range=[0, 1.05],
                       gridcolor="#232a34", zerolinecolor="#3a4453", backgroundcolor="#0b0d10"),
        ),
    )

    plot_div = fig.to_html(include_plotlyjs=False, full_html=False, div_id="plot",
                           config={"displaylogo": False, "responsive": True})

    legend = "".join(
        f'<span style="background:{DOC_TYPE_COLORS.get(t, "#4b5563")}">{t}</span>'
        for t, _ in Counter(p["doc_type"] for p in points).most_common()
    )
    prof_rows = "".join(
        f"<tr><th>{'outlier' if pr['cluster'] == -1 else 'cluster ' + str(pr['cluster'])}</th>"
        f"<td>{pr['count']} files · "
        f"{', '.join(f'{t} {n}' for t, n in pr['top_types'])}<br>"
        f"<span class='muted'>χ {', '.join(f'{c} {n}' for c, n in pr['top_chi'])} · "
        f"mean coherence {pr['mean_coherence']}</span></td></tr>"
        for pr in profiles[:14]
    )

    payload = json.dumps(points, ensure_ascii=False)
    js = (PAGE_JS.replace("__POINTS__", payload)
                 .replace("const byId", f"const MEQ = {json.dumps(MEQ_VARIABLE_NAMES)};\nconst byId"))

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FIS Cluster Map</title>
<style>{PAGE_CSS}</style>
<script>{_plotly_js()}</script>
</head><body>
<header>
  <h1>FIS <span>Cluster Map</span></h1>
  <div class="meta">{len(points):,} files · {report.get('clusters', 0)} clusters
    ({report.get('method')}) · {report.get('noise', 0)} outliers · registry: {db_path.name}</div>
</header>
<div class="wrap">
  {plot_div}
  <aside>
    <h2>Document types</h2>
    <div class="legend">{legend}</div>
    <h2>Selected file</h2>
    <div id="detail"></div>
    <h2>Clusters</h2>
    <table>{prof_rows}</table>
    <p class="muted" style="margin-top:14px">Dot size is coherence; EVIDENCE dots are
    drawn larger than their score alone would give. Confidence is shown per file in
    this panel - a low number means the type call is weak and worth checking.</p>
  </aside>
</div>
<script>{js}</script>
</body></html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="FIS 3D cluster map (reads the registry; no rescan).")
    ap.add_argument("--db", type=Path, default=DB_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--path-prefix", default="", help="Limit to files under this path")
    ap.add_argument("--cluster", choices=["dbscan", "kmeans"], default="dbscan")
    ap.add_argument("-k", type=int, default=8, help="Cluster count for kmeans")
    ap.add_argument("--eps", type=float, default=0.28, help="DBSCAN neighbourhood radius")
    ap.add_argument("--min-samples", type=int, default=4)
    ap.add_argument("--no-notes", action="store_true", help="Skip reading .fisnote sidecars")
    ap.add_argument("--no-open", action="store_true", help="Do not open the page when done")
    args = ap.parse_args()

    points = load_points(args.db, path_prefix=args.path_prefix, with_notes=not args.no_notes)
    if not points:
        print("No scored files in the registry for that scope. "
              "Run fis_folder_memory.py <folder> --tree --html --doc-types first.")
        return 1

    report   = cluster_points(points, args.cluster, args.k, args.eps, args.min_samples)
    profiles = cluster_profiles(points)
    out      = build_page(points, report, profiles, args.db, args.out)

    types = Counter(p["doc_type"] for p in points)
    print(f"FIS cluster map: {len(points)} files; {report.get('clusters')} clusters "
          f"({report.get('method')}); {report.get('noise')} outliers")
    print("  types: " + ", ".join(f"{t}={n}" for t, n in types.most_common()))
    print(f"  wrote {out}")
    if not args.no_open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
