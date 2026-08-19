"""
FIS Master Equation graph.

Nodes are files, sized by CHI score and coloured by their dominant master-
equation variable. Files that share their top-two CHI factors are joined, so
law families emerge as visible neighbourhoods.

    reports/FIS_MEQ_GRAPH.html

Rendering note: the brief asked for D3 or vis.js. Neither can be inlined
without shipping a library this machine does not hold locally, and a CDN tag
would break the no-external-runtime constraint. So the force-directed layout
is solved here in Python (Fruchterman-Reingold with Barnes-Hut-style grid
approximation) and the page renders the solved positions on a plain canvas
with pan, zoom, hover and click. Same interaction, no dependency.

    python fis_meq_graph.py
    python fis_meq_graph.py --path-prefix "D:\\01_Axioms" --max-degree 5
"""
from __future__ import annotations

import argparse
import json
import math
import random
import webbrowser
from collections import Counter, defaultdict
from pathlib import Path

from fis_vector_space import (DB_DEFAULT, MEQ_VARIABLE_COLORS, MEQ_VARIABLE_NAMES,
                              load_points)

REPORTS = Path(__file__).with_name("reports")
OUT     = REPORTS / "FIS_MEQ_GRAPH.html"

CHI_KEYS = list(MEQ_VARIABLE_NAMES)


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

def _chi_vector(chi: dict) -> list[float]:
    return [float(chi.get(k, 0) or 0) for k in CHI_KEYS]


def _cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da  = math.sqrt(sum(x * x for x in a))
    db  = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def build_edges(points: list[dict], max_degree: int = 6) -> list[dict]:
    """
    Join files that share the same top-two CHI factors.

    A naive all-pairs join inside a shared bucket is quadratic - one bucket of
    500 files would emit 125,000 edges and render as a solid disc. Each file
    therefore keeps only its strongest few partners by CHI cosine similarity,
    which preserves the family structure and drops the hairball.
    """
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for i, p in enumerate(points):
        key = tuple(sorted(p["top_two"]))
        if len(key) == 2:                      # a single shared factor is not a family
            buckets[key].append(i)

    vectors = [_chi_vector(p["chi"]) for p in points]
    seen: set[tuple[int, int]] = set()
    edges: list[dict] = []

    for key, members in buckets.items():
        if len(members) < 2:
            continue
        for i in members:
            scored = sorted(
                ((_cosine(vectors[i], vectors[j]), j) for j in members if j != i),
                key=lambda t: -t[0],
            )[:max_degree]
            for sim, j in scored:
                if sim <= 0.3:
                    continue
                pair = (i, j) if i < j else (j, i)
                if pair in seen:
                    continue
                seen.add(pair)
                edges.append({"s": pair[0], "t": pair[1], "w": round(sim, 3),
                              "k": "".join(key)})
    return edges


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def layout(points: list[dict], edges: list[dict], iterations: int = 300,
           width: float = 1600.0, height: float = 1100.0) -> None:
    """
    Fruchterman-Reingold layout, solved once here so the page opens settled.

    Repulsion is approximated on a uniform grid: only nodes within neighbouring
    cells repel each other. That keeps a corpus-scale graph tractable without
    the full Barnes-Hut tree.
    """
    n = len(points)
    if n == 0:
        return
    rng = random.Random(2828)

    # Seed from the vector space so the layout starts near a meaningful shape
    # instead of pure noise - the force pass then separates overlaps.
    pos = []
    for p in points:
        pos.append([p["x"] * width * 0.34 + rng.uniform(-24, 24),
                    p["y"] * height * 0.34 + rng.uniform(-24, 24)])

    area = width * height
    k    = math.sqrt(area / max(1, n))
    temp = width / 9.0
    cool = temp / (iterations + 1)
    cell = k * 2.0

    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in range(n)]

        grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        for i, (x, y) in enumerate(pos):
            grid[(int(x // cell), int(y // cell))].append(i)

        for (cx, cy), members in grid.items():
            near: list[int] = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    near.extend(grid.get((cx + dx, cy + dy), ()))
            for i in members:
                xi, yi = pos[i]
                for j in near:
                    if i == j:
                        continue
                    dx = xi - pos[j][0]
                    dy = yi - pos[j][1]
                    d2 = dx * dx + dy * dy
                    if d2 < 1e-6:
                        dx, dy, d2 = rng.uniform(-1, 1), rng.uniform(-1, 1), 1.0
                    d = math.sqrt(d2)
                    f = (k * k) / d
                    disp[i][0] += dx / d * f
                    disp[i][1] += dy / d * f

        for e in edges:
            i, j = e["s"], e["t"]
            dx = pos[i][0] - pos[j][0]
            dy = pos[i][1] - pos[j][1]
            d  = math.hypot(dx, dy) or 0.01
            f  = (d * d) / k * (0.5 + e["w"])
            ux, uy = dx / d * f, dy / d * f
            disp[i][0] -= ux; disp[i][1] -= uy
            disp[j][0] += ux; disp[j][1] += uy

        for i in range(n):
            # gravity keeps disconnected nodes from drifting off the canvas
            disp[i][0] -= pos[i][0] * 0.012
            disp[i][1] -= pos[i][1] * 0.012
            d = math.hypot(*disp[i]) or 1.0
            pos[i][0] += disp[i][0] / d * min(d, temp)
            pos[i][1] += disp[i][1] / d * min(d, temp)

        temp -= cool

    for p, (x, y) in zip(points, pos):
        p["gx"] = round(x, 1)
        p["gy"] = round(y, 1)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

PAGE_CSS = """
:root{color-scheme:dark;--bg:#0b0d10;--panel:#12161d;--line:#303946;
      --text:#e7edf5;--muted:#94a3b8;--accent:#d1a922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);overflow:hidden;
     font:14px/1.55 ui-sans-serif,system-ui,"Segoe UI",sans-serif}
header{padding:14px 18px;border-bottom:1px solid var(--line);background:var(--panel);
       display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
h1{margin:0;font-size:17px;letter-spacing:.4px}
h1 span{color:var(--accent)}
.meta{color:var(--muted);font-size:12px}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) 360px;height:calc(100vh - 56px)}
canvas{display:block;cursor:grab;background:var(--bg)}
canvas.drag{cursor:grabbing}
aside{border-left:1px solid var(--line);background:var(--panel);overflow-y:auto;padding:14px}
aside h2{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin:0 0 8px}
.card{border:1px solid var(--line);background:#0d1117;padding:10px;margin:0 0 12px}
.fname{font-weight:600;word-break:break-word}
code{background:#0d1117;border:1px solid var(--line);padding:1px 5px;font-size:12px;word-break:break-all}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--muted);font-weight:500;width:92px;padding:3px 6px 3px 0;vertical-align:top}
td{padding:3px 0;word-break:break-word}
.legend{display:grid;gap:4px;margin:0 0 12px}
.legend div{display:flex;align-items:center;gap:7px;font-size:11.5px}
.dot{width:11px;height:11px;border-radius:50%;flex:none}
.note{white-space:pre-wrap;font-size:11.5px;color:var(--muted);max-height:220px;overflow:auto;
      border-top:1px solid var(--line);margin-top:8px;padding-top:8px}
a{color:var(--accent)}
.muted{color:var(--muted)}
#tip{position:fixed;pointer-events:none;background:#0d1117;border:1px solid var(--line);
     padding:6px 9px;font-size:12px;max-width:340px;display:none;z-index:9}
.hint{font-size:11px;color:var(--muted);margin-top:12px}
"""

PAGE_JS = r"""
const NODES = __NODES__, EDGES = __EDGES__, MEQ = __MEQ__, COLORS = __COLORS__;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const tip = document.getElementById('tip');
let scale = 1, ox = 0, oy = 0, hover = null, selected = null, dragging = false, lx = 0, ly = 0;

function fit(){
  cv.width = cv.clientWidth * devicePixelRatio;
  cv.height = cv.clientHeight * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  draw();
}
function toScreen(n){ return [n.gx*scale+ox+cv.clientWidth/2, n.gy*scale+oy+cv.clientHeight/2]; }

function draw(){
  ctx.clearRect(0,0,cv.clientWidth,cv.clientHeight);
  ctx.lineWidth = 0.6;
  for(const e of EDGES){
    const a = NODES[e.s], b = NODES[e.t];
    const [ax,ay] = toScreen(a), [bx,by] = toScreen(b);
    const lit = selected && (selected===a || selected===b);
    ctx.strokeStyle = lit ? 'rgba(209,169,34,.75)' : 'rgba(120,135,160,.14)';
    ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(bx,by); ctx.stroke();
  }
  for(const n of NODES){
    const [x,y] = toScreen(n);
    const r = Math.max(2, n.r*scale*0.5);
    ctx.globalAlpha = n.op;
    ctx.fillStyle = COLORS[n.v] || '#4b5563';
    ctx.beginPath(); ctx.arc(x,y,r,0,6.284); ctx.fill();
    ctx.globalAlpha = 1;
    if(n===selected || n===hover){
      ctx.strokeStyle = '#d1a922'; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(x,y,r+3,0,6.284); ctx.stroke(); ctx.lineWidth = 0.6;
    }
  }
}
function pick(mx,my){
  let best=null, bd=1e9;
  for(const n of NODES){
    const [x,y]=toScreen(n); const d=Math.hypot(x-mx,y-my);
    const r=Math.max(4,n.r*scale*0.5)+3;
    if(d<r && d<bd){ bd=d; best=n; }
  }
  return best;
}
function esc(s){ return String(s ?? '').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function show(n){
  const p = document.getElementById('detail');
  if(!n){ p.innerHTML='<p class="muted">Click a node to inspect the file.</p>'; return; }
  const link = n.page ? `<a href="${n.page}#${n.id}">open in folder page</a>`
                      : '<span class="muted">no FIS.html for this folder yet</span>';
  const chi = Object.entries(n.chi).sort((a,b)=>b[1]-a[1]).filter(e=>e[1]>0)
    .map(([k,v])=>`<tr><th>${k} ${esc(MEQ[k]||'')}</th><td>${v}/3</td></tr>`).join('');
  p.innerHTML = `<div class="card">
    <div class="fname">${esc(n.name)}</div>
    <div style="margin:6px 0"><span class="dot" style="display:inline-block;background:${COLORS[n.v]}"></span>
      <b>${n.v}</b> ${esc(MEQ[n.v]||'unclassified')}</div>
    <table>
      <tr><th>Address</th><td><code>${esc(n.addr||'-')}</code></td></tr>
      <tr><th>Doc type</th><td>${esc(n.dt)} (conf ${n.conf})</td></tr>
      <tr><th>Domain</th><td>${esc(n.dom)}</td></tr>
      <tr><th>Law</th><td>${esc(n.law)}</td></tr>
      <tr><th>CHI sum</th><td>${n.sum}</td></tr>
      <tr><th>Path</th><td><code>${esc(n.path)}</code></td></tr>
      <tr><th>Open</th><td>${link}</td></tr>
    </table>
    <table style="margin-top:8px">${chi}</table>
    ${n.note ? `<div class="note">${esc(n.note)}</div>`
             : '<div class="note muted">No .fisnote sidecar on disk for this file.</div>'}</div>`;
}

cv.addEventListener('mousemove', ev=>{
  const r = cv.getBoundingClientRect(), mx = ev.clientX-r.left, my = ev.clientY-r.top;
  if(dragging){ ox += ev.clientX-lx; oy += ev.clientY-ly; lx=ev.clientX; ly=ev.clientY; draw(); return; }
  const n = pick(mx,my);
  if(n!==hover){ hover=n; draw(); }
  if(n){
    tip.style.display='block'; tip.style.left=(ev.clientX+14)+'px'; tip.style.top=(ev.clientY+14)+'px';
    tip.innerHTML = `<b>${esc(n.name)}</b><br>${esc(n.addr||'')}<br>
      ${n.v} · ${esc(MEQ[n.v]||'')}<br><span class="muted">${esc(n.path)}</span>`;
  } else tip.style.display='none';
});
cv.addEventListener('mousedown', ev=>{ dragging=true; lx=ev.clientX; ly=ev.clientY; cv.classList.add('drag'); });
addEventListener('mouseup', ()=>{ dragging=false; cv.classList.remove('drag'); });
cv.addEventListener('click', ev=>{
  const r=cv.getBoundingClientRect();
  const n=pick(ev.clientX-r.left, ev.clientY-r.top);
  selected=n; show(n); draw();
});
cv.addEventListener('wheel', ev=>{
  ev.preventDefault();
  const f = ev.deltaY<0 ? 1.12 : 1/1.12;
  scale = Math.max(0.06, Math.min(9, scale*f));
  draw();
}, {passive:false});
addEventListener('resize', fit);
fit(); show(null);
"""


def build_page(points: list[dict], edges: list[dict], db_path: Path, out: Path) -> Path:
    nodes = [{
        "id": p["file_id"], "name": p["name"], "path": p["path"], "addr": p["address"],
        "gx": p.get("gx", 0.0), "gy": p.get("gy", 0.0),
        "v": p["top_chi"], "chi": p["chi"], "sum": p["chi_sum"],
        "dt": p["doc_type"], "conf": p["confidence"], "dom": p["domain"], "law": p["law"],
        # Node radius follows CHI sum - the brief's "sized by chi score".
        "r": round(4.0 + 16.0 * min(1.0, p["chi_sum"] / 22.0), 2),
        "op": p["opacity"], "page": p["page"], "note": (p.get("fisnote") or "")[:1500],
    } for p in points]

    counts = Counter(p["top_chi"] for p in points)
    legend = "".join(
        f'<div><span class="dot" style="background:{MEQ_VARIABLE_COLORS.get(v, "#4b5563")}"></span>'
        f'<b>{v}</b>&nbsp;{MEQ_VARIABLE_NAMES.get(v, "unclassified")}&nbsp;'
        f'<span class="muted">({n})</span></div>'
        for v, n in counts.most_common()
    )

    js = (PAGE_JS.replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
                 .replace("__EDGES__", json.dumps(edges))
                 .replace("__MEQ__", json.dumps(MEQ_VARIABLE_NAMES))
                 .replace("__COLORS__", json.dumps(MEQ_VARIABLE_COLORS)))

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FIS Master Equation Graph</title>
<style>{PAGE_CSS}</style>
</head><body>
<header>
  <h1>FIS <span>Master Equation Graph</span></h1>
  <div class="meta">{len(nodes):,} files · {len(edges):,} shared-factor links ·
    registry: {db_path.name}</div>
</header>
<div class="wrap">
  <canvas id="cv"></canvas>
  <aside>
    <h2>Dominant MEQ variable</h2>
    <div class="legend">{legend}</div>
    <h2>Selected file</h2>
    <div id="detail"></div>
    <p class="hint">Node size is CHI sum; opacity is document-type confidence.
    An edge means two files share the same top-two CHI factors. Scroll to zoom,
    drag to pan, click a node to inspect it.</p>
  </aside>
</div>
<div id="tip"></div>
<script>{js}</script>
</body></html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="FIS Master Equation force graph (reads the registry).")
    ap.add_argument("--db", type=Path, default=DB_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--path-prefix", default="")
    ap.add_argument("--max-degree", type=int, default=6, help="Strongest partners kept per file")
    ap.add_argument("--iterations", type=int, default=300)
    ap.add_argument("--no-notes", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    points = load_points(args.db, path_prefix=args.path_prefix, with_notes=not args.no_notes)
    if not points:
        print("No scored files in the registry for that scope. "
              "Run fis_folder_memory.py <folder> --tree --html --doc-types first.")
        return 1

    edges = build_edges(points, max_degree=args.max_degree)
    layout(points, edges, iterations=args.iterations)
    out = build_page(points, edges, args.db, args.out)

    fams = Counter(p["top_chi"] for p in points)
    print(f"FIS MEQ graph: {len(points)} nodes; {len(edges)} edges")
    print("  dominant variable: " + ", ".join(f"{v}={n}" for v, n in fams.most_common()))
    print(f"  wrote {out}")
    if not args.no_open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
