#!/usr/bin/env python3
"""Companion Paper Mind Map — POF 2828 Pipeline Tool.

Reads companion .md files (CKG_RECORD format), extracts connections
(shared claims, tags, domains, framework keys), and generates an
interactive HTML force-directed graph.

Every time a new paper comes through the pipeline, re-run this to
regenerate the graph with the new paper integrated.

USAGE:
    python companion_mindmap.py                  # uses default OUTBOX_ROOT
    python companion_mindmap.py /path/to/outbox  # override root
    python companion_mindmap.py --threshold 0.15 # lower connection threshold
    python companion_mindmap.py --open           # auto-open in browser

Reuses the parser from companion_cluster.py (must be in the same folder).
"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# CONFIG — change this one line when you copy the folder elsewhere
# ──────────────────────────────────────────────────────────────────
OUTBOX_ROOT = r"H:\Desktop\_____pipeline-workflows-main\EVIDENCE_CHAIN_INTAKE\OUTBOX"

# Minimum composite similarity to draw an edge
EDGE_THRESHOLD = 0.12

# ──────────────────────────────────────────────────────────────────
# Import parser from companion_cluster.py
# ──────────────────────────────────────────────────────────────────
try:
    from companion_cluster import (
        scan_outbox,
        composite_similarity,
        CompanionRecord,
    )
except ImportError:
    print("ERROR: companion_cluster.py must be in the same folder.")
    print("       It provides the CKG_RECORD parser.")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# Domain → color mapping
# ──────────────────────────────────────────────────────────────────
DOMAIN_COLORS = {
    "theology":        "#e6b422",  # gold
    "physics":         "#4fc3f7",  # light blue
    "mathematics":     "#ab47bc",  # purple
    "philosophy":      "#66bb6a",  # green
    "metaphysics":     "#ff7043",  # orange
    "information theory": "#26c6da",  # cyan
    "consciousness":   "#ec407a",  # pink
    "ethics":          "#8d6e63",  # brown
    "scripture":       "#ffd54f",  # amber
    "cosmology":       "#7e57c2",  # deep purple
    "logic":           "#9ccc65",  # light green
    "epistemology":    "#5c6bc0",  # indigo
    "unification":     "#ef5350",  # red
    "neuroscience":    "#29b6f6",  # blue
    "quantum":         "#26a69a",  # teal
    "theophysics":     "#ffa726",  # deep gold
}
DEFAULT_COLOR = "#78909c"  # blue-grey


def domain_color(domain: str) -> str:
    """Get color for a domain string."""
    if not domain:
        return DEFAULT_COLOR
    key = domain.lower().strip()
    # Try exact match first
    if key in DOMAIN_COLORS:
        return DOMAIN_COLORS[key]
    # Try partial match
    for k, v in DOMAIN_COLORS.items():
        if k in key or key in k:
            return v
    return DEFAULT_COLOR


def grade_to_size(grade: str) -> int:
    """Map grade to node radius."""
    if not grade:
        return 8
    g = grade.upper().strip()
    if g.startswith("A"):
        return 18
    if g.startswith("B"):
        return 14
    if g.startswith("C"):
        return 10
    if g.startswith("D"):
        return 7
    return 5  # F


def build_graph_data(records: list[CompanionRecord], threshold: float) -> dict:
    """Build nodes and edges for the force graph."""
    nodes = []
    edges = []

    for rec in records:
        # Shorten title for display
        title = rec.paper_id or rec.filepath.stem
        if len(title) > 50:
            title = title[:47] + "..."

        tags_str = ", ".join(
            t["tag"] if isinstance(t, dict) else str(t)
            for t in (rec.tags_weighted or [])[:5]
        )

        node = {
            "id": rec.paper_id or str(rec.filepath),
            "title": title,
            "domain": rec.domain_primary or "Unknown",
            "domain2": rec.domain_secondary or "",
            "domain3": rec.domain_tertiary or "",
            "color": domain_color(rec.domain_primary),
            "size": grade_to_size(rec.grade),
            "score": rec.score_total or 0,
            "grade": rec.grade or "?",
            "coherence": rec.coherence or 0,
            "tags": tags_str,
            "finding": rec.one_sentence_finding or "",
            "build_next": rec.build_next or "",
            "governing_q": rec.governing_question or "",
            "evd_support": rec.evd_support or 0,
            "evd_counter": rec.evd_counter or 0,
            "evd_balance": rec.evd_balance or 0,
            "framework_keys": ", ".join(rec.framework_keys or []),
            "claim_ids": ", ".join(rec.claim_ids or []),
        }
        nodes.append(node)

    # Compute edges
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            sim = composite_similarity(records[i], records[j])
            if sim >= threshold:
                # Figure out what's connecting them
                connections = []
                # Check shared tags
                tags_a = {(t["tag"] if isinstance(t, dict) else str(t))
                          for t in (records[i].tags_weighted or [])}
                tags_b = {(t["tag"] if isinstance(t, dict) else str(t))
                          for t in (records[j].tags_weighted or [])}
                shared_tags = tags_a & tags_b
                if shared_tags:
                    connections.append(f"Tags: {', '.join(list(shared_tags)[:3])}")

                # Check shared domains
                doms_a = {d.strip().lower() for d in
                          [records[i].domain_primary or "",
                           records[i].domain_secondary or "",
                           records[i].domain_tertiary or ""] if d}
                doms_b = {d.strip().lower() for d in
                          [records[j].domain_primary or "",
                           records[j].domain_secondary or "",
                           records[j].domain_tertiary or ""] if d}
                shared_doms = doms_a & doms_b - {""}
                if shared_doms:
                    connections.append(f"Domains: {', '.join(list(shared_doms)[:2])}")

                # Check shared framework keys
                fk_a = set(records[i].framework_keys or [])
                fk_b = set(records[j].framework_keys or [])
                shared_fk = fk_a & fk_b
                if shared_fk:
                    connections.append(f"Keys: {', '.join(list(shared_fk)[:3])}")

                # Check shared claims
                cl_a = set(records[i].claim_ids or [])
                cl_b = set(records[j].claim_ids or [])
                shared_cl = cl_a & cl_b
                if shared_cl:
                    connections.append(f"Claims: {', '.join(list(shared_cl)[:2])}")

                edges.append({
                    "source": records[i].paper_id or str(records[i].filepath),
                    "target": records[j].paper_id or str(records[j].filepath),
                    "similarity": round(sim * 100, 1),
                    "connections": "; ".join(connections) if connections else f"{round(sim*100,1)}% composite",
                })

    return {"nodes": nodes, "edges": edges}


def generate_html(graph_data: dict, paper_count: int, edge_count: int) -> str:
    """Generate the interactive HTML mind map."""

    # Collect unique domains for the legend
    domains_seen = sorted(set(n["domain"] for n in graph_data["nodes"]))

    nodes_json = json.dumps(graph_data["nodes"])
    edges_json = json.dumps(graph_data["edges"])

    legend_items = ""
    for d in domains_seen:
        c = domain_color(d)
        legend_items += f'<span class="legend-item"><span class="legend-dot" style="background:{c}"></span>{d}</span>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Theophysics Mind Map — POF 2828</title>
<style>
:root {{
  --bg: #0a0a0f;
  --surface: #14141f;
  --border: #2a2a3a;
  --text: #e0e0e0;
  --text-dim: #888;
  --gold: #e6b422;
  --gold-dim: rgba(230, 180, 34, 0.3);
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  overflow: hidden;
  height: 100vh;
  width: 100vw;
}}
#header {{
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 10px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}}
#header h1 {{
  font-size: 16px;
  color: var(--gold);
  white-space: nowrap;
}}
#header .stats {{
  font-size: 13px;
  color: var(--text-dim);
}}
#legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
}}
.legend-item {{
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  opacity: 0.8;
  transition: opacity 0.2s;
}}
.legend-item:hover {{ opacity: 1; }}
.legend-item.dimmed {{ opacity: 0.25; }}
.legend-dot {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}}
#controls {{
  position: fixed;
  top: 52px; left: 16px;
  z-index: 100;
  display: flex;
  gap: 8px;
}}
#controls button {{
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}}
#controls button:hover {{
  border-color: var(--gold);
  color: var(--gold);
}}
#canvas {{
  position: fixed;
  top: 0; left: 0;
  width: 100vw;
  height: 100vh;
}}
#tooltip {{
  position: fixed;
  display: none;
  background: var(--surface);
  border: 1px solid var(--gold);
  border-radius: 6px;
  padding: 12px 16px;
  max-width: 380px;
  font-size: 13px;
  line-height: 1.5;
  z-index: 200;
  pointer-events: none;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}}
#tooltip .tt-title {{
  font-weight: 600;
  color: var(--gold);
  margin-bottom: 6px;
  font-size: 14px;
}}
#tooltip .tt-row {{
  display: flex;
  gap: 8px;
}}
#tooltip .tt-label {{
  color: var(--text-dim);
  min-width: 70px;
  flex-shrink: 0;
}}
#tooltip .tt-val {{
  color: var(--text);
}}
#detail-panel {{
  position: fixed;
  top: 50px; right: 0;
  width: 340px;
  height: calc(100vh - 50px);
  background: var(--surface);
  border-left: 1px solid var(--border);
  z-index: 100;
  overflow-y: auto;
  padding: 16px;
  transform: translateX(100%);
  transition: transform 0.3s ease;
}}
#detail-panel.open {{
  transform: translateX(0);
}}
#detail-panel h2 {{
  color: var(--gold);
  font-size: 15px;
  margin-bottom: 12px;
}}
#detail-panel .dp-section {{
  margin-bottom: 12px;
}}
#detail-panel .dp-label {{
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}}
#detail-panel .dp-val {{
  font-size: 13px;
  line-height: 1.5;
}}
#detail-panel .dp-close {{
  position: absolute;
  top: 12px; right: 12px;
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 18px;
}}
#detail-panel .dp-connections {{
  margin-top: 8px;
}}
#detail-panel .dp-conn-item {{
  background: rgba(230,180,34,0.08);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 10px;
  margin-bottom: 6px;
  font-size: 12px;
  cursor: pointer;
}}
#detail-panel .dp-conn-item:hover {{
  border-color: var(--gold-dim);
}}
#search-box {{
  position: fixed;
  top: 52px; right: 16px;
  z-index: 100;
}}
#search-box input {{
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  width: 200px;
}}
#search-box input:focus {{
  border-color: var(--gold);
  outline: none;
}}
</style>
</head>
<body>
<div id="header">
  <h1>THEOPHYSICS MIND MAP</h1>
  <div class="stats">{paper_count} papers &middot; {edge_count} connections</div>
  <div id="legend">{legend_items}</div>
</div>

<div id="controls">
  <button onclick="resetView()">Reset View</button>
  <button onclick="togglePhysics()">Freeze/Unfreeze</button>
</div>

<div id="search-box">
  <input type="text" id="search" placeholder="Search papers..." oninput="onSearch(this.value)">
</div>

<canvas id="canvas"></canvas>

<div id="tooltip"></div>

<div id="detail-panel">
  <button class="dp-close" onclick="closePanel()">&times;</button>
  <div id="dp-content"></div>
</div>

<script>
// ── Data ──
const nodes = {nodes_json};
const edges = {edges_json};

// ── Canvas setup ──
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
let W, H;
function resize() {{
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
}}
resize();
window.addEventListener('resize', resize);

// ── Simulation state ──
let simRunning = true;
const DAMPING = 0.92;
const REPULSION = 2000;
const ATTRACTION = 0.008;
const REST_LENGTH = 120;
const CENTER_PULL = 0.0005;

// Initialize positions
nodes.forEach((n, i) => {{
  const angle = (i / nodes.length) * Math.PI * 2;
  const r = 150 + Math.random() * 100;
  n.x = W/2 + Math.cos(angle) * r;
  n.y = H/2 + Math.sin(angle) * r;
  n.vx = 0;
  n.vy = 0;
  n._visible = true;
}});

// Build adjacency for quick lookup
const nodeMap = {{}};
nodes.forEach(n => nodeMap[n.id] = n);
const adj = {{}};
nodes.forEach(n => adj[n.id] = []);
edges.forEach(e => {{
  adj[e.source].push(e);
  adj[e.target].push(e);
}});

// ── Camera ──
let camX = 0, camY = 0, camZoom = 1;
let dragStart = null, dragCam = null;
let hoveredNode = null, selectedNode = null;

function screenToWorld(sx, sy) {{
  return [(sx - W/2)/camZoom + W/2 - camX, (sy - H/2)/camZoom + H/2 - camY];
}}
function worldToScreen(wx, wy) {{
  return [(wx - W/2 + camX)*camZoom + W/2, (wy - H/2 + camY)*camZoom + H/2];
}}

// ── Physics step ──
function step() {{
  if (!simRunning) return;
  const visible = nodes.filter(n => n._visible);

  // Repulsion (all pairs)
  for (let i = 0; i < visible.length; i++) {{
    for (let j = i+1; j < visible.length; j++) {{
      const a = visible[i], b = visible[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let d2 = dx*dx + dy*dy;
      if (d2 < 1) d2 = 1;
      const f = REPULSION / d2;
      const d = Math.sqrt(d2);
      const fx = (dx/d)*f, fy = (dy/d)*f;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    }}
  }}

  // Attraction (edges)
  edges.forEach(e => {{
    const a = nodeMap[e.source], b = nodeMap[e.target];
    if (!a || !b || !a._visible || !b._visible) return;
    let dx = b.x - a.x, dy = b.y - a.y;
    let d = Math.sqrt(dx*dx + dy*dy);
    if (d < 1) d = 1;
    const f = (d - REST_LENGTH) * ATTRACTION * (e.similarity/100);
    const fx = (dx/d)*f, fy = (dy/d)*f;
    a.vx += fx; a.vy += fy;
    b.vx -= fx; b.vy -= fy;
  }});

  // Center pull
  visible.forEach(n => {{
    n.vx += (W/2 - n.x) * CENTER_PULL;
    n.vy += (H/2 - n.y) * CENTER_PULL;
  }});

  // Integrate
  visible.forEach(n => {{
    n.vx *= DAMPING;
    n.vy *= DAMPING;
    n.x += n.vx;
    n.y += n.vy;
  }});
}}

// ── Render ──
function render() {{
  ctx.clearRect(0, 0, W, H);
  ctx.save();
  ctx.translate(W/2, H/2);
  ctx.scale(camZoom, camZoom);
  ctx.translate(-W/2 + camX, -H/2 + camY);

  // Edges
  edges.forEach(e => {{
    const a = nodeMap[e.source], b = nodeMap[e.target];
    if (!a || !b || !a._visible || !b._visible) return;
    const isHighlight = selectedNode &&
      (e.source === selectedNode.id || e.target === selectedNode.id);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    if (isHighlight) {{
      ctx.strokeStyle = 'rgba(230,180,34,0.6)';
      ctx.lineWidth = 2;
    }} else {{
      const alpha = Math.min(0.5, e.similarity / 100);
      ctx.strokeStyle = `rgba(255,255,255,${{alpha}})`;
      ctx.lineWidth = 0.5 + (e.similarity/100);
    }}
    ctx.stroke();
  }});

  // Nodes
  nodes.forEach(n => {{
    if (!n._visible) return;
    const isSelected = selectedNode && selectedNode.id === n.id;
    const isConnected = selectedNode && adj[selectedNode.id].some(
      e => e.source === n.id || e.target === n.id
    );
    const dimmed = selectedNode && !isSelected && !isConnected;

    ctx.beginPath();
    ctx.arc(n.x, n.y, n.size, 0, Math.PI*2);

    if (dimmed) {{
      ctx.fillStyle = n.color + '33';
    }} else {{
      ctx.fillStyle = n.color;
    }}
    ctx.fill();

    if (isSelected) {{
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }} else if (hoveredNode === n) {{
      ctx.strokeStyle = 'rgba(255,255,255,0.5)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }}

    // Label (show when zoomed in or when selected/hovered)
    if (camZoom > 0.8 || isSelected || hoveredNode === n) {{
      const label = n.title.length > 30 ? n.title.slice(0,27) + '...' : n.title;
      ctx.font = `${{isSelected ? 'bold ' : ''}}${{10/Math.max(camZoom,0.5)}}px sans-serif`;
      ctx.fillStyle = dimmed ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.85)';
      ctx.textAlign = 'center';
      ctx.fillText(label, n.x, n.y + n.size + 12);
    }}
  }});

  ctx.restore();
}}

// ── Interaction ──
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.9 : 1.1;
  camZoom = Math.max(0.1, Math.min(5, camZoom * factor));
}});

canvas.addEventListener('mousedown', e => {{
  dragStart = [e.clientX, e.clientY];
  dragCam = [camX, camY];
}});

canvas.addEventListener('mousemove', e => {{
  if (dragStart) {{
    camX = dragCam[0] + (e.clientX - dragStart[0])/camZoom;
    camY = dragCam[1] + (e.clientY - dragStart[1])/camZoom;
    return;
  }}

  const [wx, wy] = screenToWorld(e.clientX, e.clientY);
  hoveredNode = null;
  for (const n of nodes) {{
    if (!n._visible) continue;
    const dx = n.x - wx, dy = n.y - wy;
    if (dx*dx + dy*dy < (n.size + 4) * (n.size + 4)) {{
      hoveredNode = n;
      break;
    }}
  }}

  const tip = document.getElementById('tooltip');
  if (hoveredNode) {{
    canvas.style.cursor = 'pointer';
    const n = hoveredNode;
    tip.innerHTML = `
      <div class="tt-title">${{n.title}}</div>
      <div class="tt-row"><span class="tt-label">Domain</span><span class="tt-val">${{n.domain}}${{n.domain2 ? ' / '+n.domain2 : ''}}</span></div>
      <div class="tt-row"><span class="tt-label">Score</span><span class="tt-val">${{n.score}} (${{n.grade}})</span></div>
      <div class="tt-row"><span class="tt-label">Evidence</span><span class="tt-val">+${{n.evd_support}} / -${{n.evd_counter}} = ${{n.evd_balance}}</span></div>
      <div class="tt-row"><span class="tt-label">Tags</span><span class="tt-val">${{n.tags || 'none'}}</span></div>
      ${{n.finding ? '<div style="margin-top:6px;font-style:italic;color:#ccc;font-size:12px">'+n.finding+'</div>' : ''}}
    `;
    tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX + 12, W - 400) + 'px';
    tip.style.top = Math.min(e.clientY + 12, H - 200) + 'px';
  }} else {{
    canvas.style.cursor = 'grab';
    tip.style.display = 'none';
  }}
}});

canvas.addEventListener('mouseup', e => {{
  if (dragStart) {{
    const dx = e.clientX - dragStart[0];
    const dy = e.clientY - dragStart[1];
    if (dx*dx + dy*dy < 9 && hoveredNode) {{
      selectNode(hoveredNode);
    }} else if (dx*dx + dy*dy < 9) {{
      selectNode(null);
    }}
  }}
  dragStart = null;
}});

function selectNode(n) {{
  selectedNode = n;
  const panel = document.getElementById('detail-panel');
  if (!n) {{
    panel.classList.remove('open');
    return;
  }}
  const conns = adj[n.id] || [];
  let connHtml = '';
  conns.forEach(e => {{
    const otherId = e.source === n.id ? e.target : e.source;
    const other = nodeMap[otherId];
    if (!other) return;
    connHtml += `<div class="dp-conn-item" onclick="selectNode(nodeMap['${{otherId}}'])">
      <strong>${{other.title}}</strong><br>
      <span style="color:var(--text-dim)">${{e.similarity}}% — ${{e.connections}}</span>
    </div>`;
  }});

  document.getElementById('dp-content').innerHTML = `
    <h2>${{n.title}}</h2>
    <div class="dp-section">
      <div class="dp-label">Domain</div>
      <div class="dp-val">${{n.domain}}${{n.domain2 ? ' / '+n.domain2 : ''}}${{n.domain3 ? ' / '+n.domain3 : ''}}</div>
    </div>
    <div class="dp-section">
      <div class="dp-label">Score / Grade</div>
      <div class="dp-val">${{n.score}} (${{n.grade}}) &middot; Coherence: ${{n.coherence}}</div>
    </div>
    <div class="dp-section">
      <div class="dp-label">Evidence</div>
      <div class="dp-val">Support: ${{n.evd_support}} &middot; Counter: ${{n.evd_counter}} &middot; Balance: ${{n.evd_balance}}</div>
    </div>
    ${{n.governing_q ? '<div class="dp-section"><div class="dp-label">Governing Question</div><div class="dp-val">'+n.governing_q+'</div></div>' : ''}}
    ${{n.finding ? '<div class="dp-section"><div class="dp-label">Finding</div><div class="dp-val">'+n.finding+'</div></div>' : ''}}
    ${{n.framework_keys ? '<div class="dp-section"><div class="dp-label">Framework Keys</div><div class="dp-val">'+n.framework_keys+'</div></div>' : ''}}
    ${{n.claim_ids ? '<div class="dp-section"><div class="dp-label">Claim IDs</div><div class="dp-val">'+n.claim_ids+'</div></div>' : ''}}
    ${{n.tags ? '<div class="dp-section"><div class="dp-label">Tags</div><div class="dp-val">'+n.tags+'</div></div>' : ''}}
    ${{n.build_next ? '<div class="dp-section"><div class="dp-label">Build Next</div><div class="dp-val" style="color:var(--gold)">'+n.build_next+'</div></div>' : ''}}
    <div class="dp-section dp-connections">
      <div class="dp-label">Connections (${{conns.length}})</div>
      ${{connHtml || '<div class="dp-val" style="color:var(--text-dim)">No connections above threshold</div>'}}
    </div>
  `;
  panel.classList.add('open');
}}

function closePanel() {{
  selectedNode = null;
  document.getElementById('detail-panel').classList.remove('open');
}}

// ── Controls ──
function resetView() {{
  camX = 0; camY = 0; camZoom = 1;
  selectedNode = null;
  closePanel();
}}

function togglePhysics() {{
  simRunning = !simRunning;
}}

// ── Search ──
function onSearch(query) {{
  const q = query.toLowerCase().trim();
  if (!q) {{
    nodes.forEach(n => n._visible = true);
    return;
  }}
  nodes.forEach(n => {{
    n._visible =
      n.title.toLowerCase().includes(q) ||
      n.domain.toLowerCase().includes(q) ||
      n.tags.toLowerCase().includes(q) ||
      n.finding.toLowerCase().includes(q) ||
      (n.framework_keys && n.framework_keys.toLowerCase().includes(q));
  }});
}}

// ── Legend filtering ──
document.querySelectorAll('.legend-item').forEach(item => {{
  item.addEventListener('click', () => {{
    const domain = item.textContent.trim();
    const isDimmed = item.classList.contains('dimmed');
    if (isDimmed) {{
      // Show all
      document.querySelectorAll('.legend-item').forEach(i => i.classList.remove('dimmed'));
      nodes.forEach(n => n._visible = true);
    }} else {{
      // Filter to this domain
      document.querySelectorAll('.legend-item').forEach(i => {{
        if (i.textContent.trim() !== domain) i.classList.add('dimmed');
        else i.classList.remove('dimmed');
      }});
      nodes.forEach(n => {{
        n._visible = n.domain === domain || n.domain2 === domain || n.domain3 === domain;
      }});
    }}
  }});
}});

// ── Main loop ──
function loop() {{
  step();
  render();
  requestAnimationFrame(loop);
}}
loop();
</script>
</body>
</html>"""
    return html


def main():
    root = OUTBOX_ROOT
    threshold = EDGE_THRESHOLD
    auto_open = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--threshold" and i + 1 < len(args):
            threshold = float(args[i + 1])
            i += 2
        elif args[i] == "--open":
            auto_open = True
            i += 1
        elif args[i] == "--help":
            print(__doc__)
            return
        elif not args[i].startswith("-"):
            root = args[i]
            i += 1
        else:
            i += 1

    print(f"Scanning: {root}")
    records = scan_outbox(root)
    print(f"Parsed {len(records)} companion papers.")

    if not records:
        print("No companion papers found. Nothing to map.")
        return

    print(f"Computing connections (threshold: {threshold*100:.0f}%)...")
    graph_data = build_graph_data(records, threshold)
    edge_count = len(graph_data["edges"])
    print(f"Found {edge_count} connections between papers.")

    # Write output
    output_dir = os.path.join(root, "_output")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "MIND_MAP.html")

    html = generate_html(graph_data, len(records), edge_count)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nMind map written to: {out_path}")
    print(f"  {len(records)} nodes, {edge_count} edges")

    # Also write the graph data as JSON
    json_path = os.path.join(output_dir, "mindmap_graph.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)
    print(f"  Graph data: {json_path}")

    if auto_open:
        webbrowser.open(f"file:///{out_path}")


if __name__ == "__main__":
    main()
