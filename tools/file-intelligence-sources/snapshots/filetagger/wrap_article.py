#!/usr/bin/env python3
"""
Article Template Wrapper v3 — spaced proportional pill top bar
==============================================================
Home | [domain pills] | ← Prev [TABS] Next → | [claim pills] | Series

Usage:
  python wrap_article.py article.html --prev prev.html --next next.html
  python wrap_article.py folder/ --recursive
"""
import argparse, json, re, sys
from pathlib import Path
from datetime import datetime

SERIES_CONFIG = {
    "mda": {"accent":"#991b1b","home":"../00-entry-and-series-map/index.html","series":"../00-entry-and-series-map/index.html"},
    "consciousness": {"accent":"#14b8a6","home":"../index.html","series":"index.html"},
    "convergence": {"accent":"#d4af37","home":"../index.html","series":"index.html"},
    "gtq": {"accent":"#d4af37","home":"../index.html","series":"index.html"},
    "default": {"accent":"#d4af37","home":"https://faiththruphysics.com","series":"https://faiththruphysics.com"},
}
DOMAIN_COLORS = {
    "physics":"#8aa1ff","theology":"#d6aa45","epistemology":"#7cc7ff",
    "formal_math":"#c79bff","information":"#38bdf8","ethics":"#ff7d90",
    "psychology":"#ffb86b","sociology":"#8fe6b0","history":"#aeb8d6",
}

def hex_to_rgb(h):
    h = h.lstrip('#')
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"

def build_topbar(accent, home, series_link, prev_link, next_link, domains, claims, ts):
    dpills = ""
    for name, pct, color in domains:
        label = f"{name} {pct}%" if pct >= 8 else f"{pct}%"
        dpills += f'<span class="tp-pill" style="width:{pct}%;background:rgba({hex_to_rgb(color)},.22);color:{color}">{label}</span>\n'
    return f"""<!-- BEGIN: TOPBAR V3 PILL | {ts} -->
<style>
.tp-bar{{position:sticky;top:0;z-index:1000;background:#080808;border-bottom:1px solid #1a1a1a;font-family:system-ui,sans-serif}}
.tp-row{{display:flex;align-items:center;padding:8px 16px;justify-content:space-between}}
.tp-edge{{font-size:11px;color:#555;text-decoration:none;cursor:pointer;white-space:nowrap;padding:0 8px}}
.tp-edge:hover{{color:{accent}}}
.tp-zone{{display:flex;gap:2px;align-items:center;flex:1;padding:0 12px;max-width:280px}}
.tp-zone-r{{justify-content:flex-end}}
.tp-pill{{display:flex;align-items:center;justify-content:center;padding:7px 0;font-size:9px;font-weight:600;border-radius:14px;cursor:pointer;white-space:nowrap;transition:all .15s;overflow:hidden;line-height:1}}
.tp-pill:hover{{filter:brightness(1.3)}}
.tp-center{{display:flex;align-items:center;gap:0;flex-shrink:0}}
.tp-nav{{font-size:11px;color:#444;cursor:pointer;white-space:nowrap;padding:0 8px;text-decoration:none}}
.tp-nav:hover{{color:#aaa}}
.tp-tabs{{display:flex;gap:3px;align-items:center;padding:0 6px}}
.tp-tab{{padding:10px 14px;font-size:11px;font-weight:500;color:#555;background:#0c0c0c;border:1px solid #1a1a1a;border-radius:6px;cursor:pointer;text-transform:uppercase;letter-spacing:.8px;transition:all .15s;line-height:1;white-space:nowrap;font-family:system-ui,sans-serif}}
.tp-tab:hover{{color:#ccc;background:#141414;border-color:#333}}
.tp-tab.active{{color:#fff;background:{accent};border-color:{accent}}}
.tp-tab.glow{{color:#d4af37;border-color:rgba(212,175,55,.4);background:rgba(212,175,55,.06)}}
.tp-tab.glow:hover{{background:rgba(212,175,55,.12)}}
</style>
<div class="tp-bar">
<div class="tp-row">
<a class="tp-edge" href="{home}">Home</a>
<div class="tp-zone">
{dpills}</div>
<div class="tp-center">
<a class="tp-nav" href="{prev_link}">&larr; Prev</a>
<div class="tp-tabs" role="tablist">
<button class="tp-tab" data-mode="simple">Simple</button>
<button class="tp-tab active" data-mode="readable">Readable</button>
<button class="tp-tab" data-mode="scholarly">Scholarly</button>
<button class="tp-tab glow" data-mode="proof">Proof</button>
</div>
<a class="tp-nav" href="{next_link}">Next &rarr;</a>
</div>
<div class="tp-zone tp-zone-r">
<span class="tp-pill" style="width:{claims['what']}%;background:rgba(24,95,165,.25);color:#7bb8f0">What {claims['what']}%</span>
<span class="tp-pill" style="width:{claims['how']}%;background:rgba(15,110,86,.25);color:#6dd4b1">How {claims['how']}%</span>
<span class="tp-pill" style="width:{claims['why']}%;background:rgba(133,79,11,.25);color:#e8b84a">Why {claims['why']}%</span>
</div>
<a class="tp-edge" href="{series_link}">Series</a>
</div>
</div>
<!-- END: TOPBAR V3 PILL -->
"""

DISCLAIMER = """<!-- BEGIN: DISCLAIMER -->
<footer style="max-width:760px;margin:3rem auto;padding:24px;background:#0a0a0a;border:1px solid #1a1a1a;border-radius:8px;font-family:Georgia,serif;font-size:15px;line-height:1.7;color:#999">
<p style="margin:0 0 12px">The math is here. The proofs compile. The structures match or they don't. What we can't formalize — and wouldn't try to — is what happens inside you when you see it. That's yours. That's the one variable in the equation that no one else gets to set for you.</p>
<p style="margin:0;font-size:13px;color:#666">Framework, theological claims, and final interpretive responsibility: David Lowe. Mathematical formalization, software infrastructure, and corpus analysis: AI-assisted under David Lowe's direction. Physics-theology bridge proposals: collaborative, with David Lowe responsible for bridge selection, interpretation, and final claims.</p>
</footer>
<!-- END: DISCLAIMER -->"""

def get_claims(path):
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from claim_jurisdiction import read_text, split_sentences, classify_sentence, normalize
        text = read_text(Path(path))
        sents = split_sentences(text)
        t = {"what":0,"how":0,"why":0}
        for s in sents:
            w,h,y = classify_sentence(s)
            wp,hp,yp = normalize(w,h,y)
            t["what"]+=wp; t["how"]+=hp; t["why"]+=yp
        total = t["what"]+t["how"]+t["why"]
        if total<=0: return {"what":33,"how":34,"why":33}
        return {k:round(v/total*100) for k,v in t.items()}
    except Exception as e:
        print(f"  claims failed: {e}")
        return {"what":33,"how":34,"why":33}

def get_domains(path):
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from chi_pipeline import run_pipeline
        text = Path(path).read_text(encoding="utf-8",errors="replace")
        ext = Path(path).suffix.lower()
        rec = run_pipeline(text, str(path), "file", ["domain"], ext)
        if rec.domains and rec.domains.get("composition"):
            return [(n.replace("_"," ").title(), round(p), DOMAIN_COLORS.get(n,"#888"))
                    for n,p in sorted(rec.domains["composition"].items(), key=lambda x:-x[1]) if p>=4]
        return [("General",100,"#888")]
    except Exception as e:
        print(f"  domains failed: {e}")
        return [("General",100,"#888")]

def detect_series(path):
    p = str(path).lower()
    for key in ["mda","consciousness","convergence","gtq"]:
        if key in p: return key
    return "default"

def strip_old(html):
    html = re.sub(r'<div class="mda-topbar-v2".*?<!-- END MDA UNIFIED TOP BAR v2 -->','',html,flags=re.DOTALL)
    html = re.sub(r'<!-- BEGIN: TOPBAR V3.*?<!-- END: TOPBAR V3 PILL -->','',html,flags=re.DOTALL)
    html = re.sub(r'<nav style="position:sticky[^"]*".*?</nav>','',html,flags=re.DOTALL)
    html = re.sub(r'<!-- BEGIN: DISCLAIMER -->.*?<!-- END: DISCLAIMER -->','',html,flags=re.DOTALL)
    return html

def wrap(path, prev="#", nxt="#", series=None, in_place=False):
    p = Path(path)
    html = p.read_text(encoding="utf-8",errors="replace")
    if not series: series = detect_series(p)
    cfg = SERIES_CONFIG.get(series, SERIES_CONFIG["default"])
    claims = get_claims(p); print(f"  W{claims['what']} H{claims['how']} Y{claims['why']}", end=" ")
    domains = get_domains(p); print(f"| {len(domains)}dom")
    html = strip_old(html)
    tb = build_topbar(cfg["accent"],cfg["home"],cfg["series"],prev,nxt,domains,claims,datetime.now().isoformat())
    m = re.search(r'<body[^>]*>',html,re.I)
    pos = m.end() if m else 0
    html = html[:pos]+"\n"+tb+"\n"+html[pos:]
    m2 = re.search(r'</body>',html,re.I)
    pos2 = m2.start() if m2 else len(html)
    html = html[:pos2]+"\n"+DISCLAIMER+"\n"+html[pos2:]
    out = p if in_place else p.parent/(p.stem+"-wrapped"+p.suffix)
    out.write_text(html,encoding="utf-8")
    return str(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--prev",default="#")
    ap.add_argument("--next",default="#")
    ap.add_argument("--series")
    ap.add_argument("--in-place",action="store_true")
    ap.add_argument("--recursive",action="store_true")
    a = ap.parse_args()
    t = Path(a.path)
    if t.is_file():
        print(f"  {t.name}"); wrap(t,a.prev,a.next,a.series,a.in_place)
    elif t.is_dir():
        g = t.rglob("*.html") if a.recursive else t.glob("*.html")
        fs = sorted([f for f in g if "-wrapped" not in f.stem and f.name!="index.html"])
        for i,f in enumerate(fs):
            pv = fs[i-1].name if i>0 else "index.html"
            nx = fs[i+1].name if i<len(fs)-1 else "index.html"
            print(f"[{i+1}/{len(fs)}] {f.name}",end=" ")
            wrap(f,pv,nx,a.series,a.in_place)
        print(f"\nDone: {len(fs)} articles")

if __name__=="__main__": raise SystemExit(main())
