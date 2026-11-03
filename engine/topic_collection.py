"""Topic collection orchestration over existing Drive Harvester functions. No model calls."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from gui import drive_harvester as harvester
from engine.understand import SKIP_DIRS as INVENTORY_SKIP, NEVER_WALK

EXTENSIONS = set(harvester.EXTENSIONS) | {".lean", ".markdown"}


def hash_plan(plan):
    return hashlib.sha256(json.dumps({k: v for k, v in plan.items() if k != "plan_sha256"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def tier(path):
    parts = [p.casefold() for p in Path(path).parts]
    if ".trash" in parts:
        return "recovered_from_trash"
    if any("archive" in p or p in {"_old", "older", "backup", "backups"} for p in parts):
        return "archive"
    return "active"


def plan_collection(request, *, exclude=(), progress=print, stop=None):
    topic = request.get("topic", "").strip()
    if not topic or not request.get("roots"):
        raise ValueError("A topic and explicit roots are required")
    roots = [Path(p).expanduser().resolve() for p in request["roots"]]
    excluded = [Path(p).resolve() for p in exclude]
    profile = harvester.profile_for(topic, request.get("synonyms", []))
    allowed_fields = {"filename", "folder", "heading", "body", "tags", "sidecar"}
    profile["fields"] = request.get("fields", sorted(allowed_fields))
    if not profile["fields"] or set(profile["fields"]) - allowed_fields:
        raise ValueError("Choose valid search fields")
    extensions = set(request.get("extensions", EXTENSIONS))
    if not extensions or extensions - EXTENSIONS:
        raise ValueError("Choose supported file extensions")
    recover = bool(request.get("include_trash", True))
    limit = int(request.get("max_files", 5000))
    if limit < 1:
        raise ValueError("max_files must be positive")
    files, events, visited, scanned = [], [], set(), 0
    partial = False
    cancelled = False
    seeds = request.get("seeds", [])
    for root in roots:
        if stop and stop():
            cancelled = partial = True
            break
        if not root.exists() or root.is_symlink() or getattr(root, "is_junction", lambda: False)():
            events.append({"path": str(root), "reason": "missing_or_linked_root"})
            partial = True
            continue
        walk_root = root if root.is_dir() else root.parent
        entries = os.walk(root, followlinks=False, onerror=lambda e: events.append({"path": str(e.filename), "reason": str(e)})) if root.is_dir() else [(str(root.parent), [], [root.name])]
        for directory, dirs, names in entries:
            if stop and stop():
                cancelled = partial = True
                break
            kept = []
            for name in dirs:
                child = Path(directory) / name
                blocked = name.casefold() in (harvester.SKIP_DIRS | INVENTORY_SKIP | NEVER_WALK)
                if name.casefold() == ".trash":
                    blocked = not recover
                if blocked or name.startswith("$") or child.is_symlink() or getattr(child, "is_junction", lambda: False)() or any(child.resolve().is_relative_to(p) for p in excluded):
                    events.append({"path": str(child), "reason": "excluded_directory"})
                else:
                    kept.append(name)
            dirs[:] = kept
            for name in names:
                path = Path(directory) / name
                if path.suffix.lower() not in extensions or path.is_symlink():
                    continue
                identity = os.path.normcase(str(path.resolve()))
                if identity in visited or any(path.resolve().is_relative_to(p) for p in excluded):
                    continue
                visited.add(identity)
                if stop and stop():
                    cancelled = partial = True
                    break
                if scanned >= limit:
                    partial = True
                    break
                scanned += 1
                if scanned % 100 == 0:
                    progress(f"SEARCH {scanned} files · {path}")
                try:
                    if path.stat().st_size > harvester.MAX_BYTES:
                        events.append({"path": str(path), "reason": "over_size_limit"})
                        continue
                    needs_text = bool(set(profile["fields"]) & {"heading", "body", "tags"})
                    extracted = harvester.read_text(path) if needs_text else ""
                    if needs_text and not extracted:
                        events.append({"path": str(path), "reason": "empty_or_unextractable_text"})
                    elif len(extracted) >= 400000:
                        events.append({"path": str(path), "reason": "text_limit_reached"})
                    row = harvester.score_file(path, profile, text=extracted)
                    folder_match = "folder" in profile["fields"] and any(topic.casefold() in part.casefold() for part in path.relative_to(walk_root).parts[:-1])
                    seed_match = [s["name"] for s in seeds if any(token.casefold() in str(path).casefold() for token in s.get("path_contains", []))]
                    if not row and (folder_match or seed_match):
                        row = harvester.bare_row(path)
                        row.update(confidence=40, signals=["topic folder" if folder_match else "known source candidate"])
                    if row:
                        row.update(scan_root=str(walk_root), source_tier=tier(path), sha256=harvester.sha256(str(path)),
                                   seeds=seed_match, text_limit_chars=400000,
                                   extraction_status="at_text_limit" if len(extracted) >= 400000 else "text_available" if extracted else "empty_or_unextractable")
                        if row["confidence"] >= float(request.get("minimum_score", 0)):
                            files.append(row)
                except (OSError, ValueError) as exc:
                    events.append({"path": str(path), "reason": str(exc)})
            if cancelled or partial and scanned >= limit:
                break
        if cancelled or partial and scanned >= limit:
            break
    groups = defaultdict(list)
    for row in files:
        groups[row["sha256"]].append(row["path"])
    checks = [{"name": s["name"], "status": "candidate_found" if any(s["name"] in f["seeds"] for f in files) else "not_found_in_this_scope",
               "matches": [f["path"] for f in files if s["name"] in f["seeds"]]} for s in seeds]
    plan = {"schema": "topic-collection/1", "topic": topic, "profile": profile, "roots": list(map(str, roots)),
            "include_trash": recover, "extensions": sorted(extensions), "cancelled": cancelled,
            "scanned_files": scanned, "partial": partial or any(e["reason"] != "excluded_directory" for e in events),
            "files": files, "events": events, "seed_checks": checks, "seed_rules": seeds,
            "exact_duplicate_groups": [paths for paths in groups.values() if len(paths) > 1],
            "next_stages": {"publication_families": "available_existing_scanner_not_run", "classification": "existing_FIS_not_run",
                            "anatomy_spec_09": "requires_locating_spec", "canon_guard": "requires_locating_contract_and_rulings", "definitive_article": "not_started"}}
    plan["plan_sha256"] = hash_plan(plan)
    return plan


def review_html(plan):
    embedded = json.dumps(plan, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Topic collection review</title>
<style>body{background:#10151e;color:#e5e9ef;font:15px system-ui;margin:30px}h1{color:#ddbb73}button,input{font:inherit;padding:9px}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #374151;overflow-wrap:anywhere}td.path{max-width:650px}.recovered_from_trash{color:#ffb27f}.archive{color:#c5afff}.note{color:#aab8cd}details{margin:12px 0}pre{white-space:pre-wrap}thead{position:sticky;top:0;background:#10151e}</style>
<h1 id="title"></h1><p id="stats"></p><p class="note">Copy-only collection plan. Scores rank topic matches; they are not probabilities or canonical rulings. Archived/trash sources remain flagged. All related drafts are retained unless you exclude them.</p><button id="all">Select all visible</button> <button id="none">Clear selection</button> <button id="save">Export selection JSON</button><p><input id="filter" aria-label="Filter results" placeholder="Filter paths or recovery tier"></p><div id="seeds"></div><table><thead><tr><th>Collect</th><th>Source / provenance</th><th>Tier</th><th>Signals</th></tr></thead><tbody id="rows"></tbody></table>
<script id="plan" type="application/json">''' + embedded + '''</script><script>
const P=JSON.parse(document.getElementById('plan').textContent),selected=new Set();const $=id=>document.getElementById(id);function text(tag,value){const n=document.createElement(tag);n.textContent=value;return n;}function visible(){const q=$('filter').value.toLowerCase();return P.files.filter(f=>(f.path+' '+f.source_tier).toLowerCase().includes(q));}function render(){$('rows').replaceChildren();for(const f of visible()){const tr=document.createElement('tr'),box=document.createElement('input');box.type='checkbox';box.checked=selected.has(f.path);box.setAttribute('aria-label','Select '+f.name);box.onchange=()=>box.checked?selected.add(f.path):selected.delete(f.path);const td=document.createElement('td');td.append(box);const path=text('td',f.path);path.className='path';const tier=text('td',f.source_tier);tier.className=f.source_tier;tr.append(td,path,tier,text('td',f.signals.join(', ')+' · '+f.extraction_status));$('rows').append(tr);}}$('title').textContent=P.topic+' · Collection review';$('stats').textContent=P.scanned_files+' inspected · '+P.files.length+' matches · '+P.exact_duplicate_groups.length+' byte-exact duplicate groups · '+(P.partial?'PARTIAL SCOPE — see plan events':'completed selected scope');for(const s of P.seed_checks)$('seeds').append(text('p',s.name+': '+s.status));$('filter').oninput=render;$('all').onclick=()=>{visible().forEach(f=>selected.add(f.path));render()};$('none').onclick=()=>{selected.clear();render()};$('save').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({plan_sha256:P.plan_sha256,selected_paths:[...selected]},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='selection.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};render();
</script></html>'''


def collect_selection(plan, selection, destination, *, layout="flat", stop=None, progress=None):
    if layout not in {"flat", "extension"}:
        raise ValueError("Choose a flat collection or grouping by file type")
    if plan.get("plan_sha256") != hash_plan(plan) or selection.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("Plan/selection version mismatch")
    by_path = {row["path"]: row for row in plan["files"]}
    selected = list(dict.fromkeys(selection.get("selected_paths", [])))
    if not selected or any(path not in by_path for path in selected):
        raise ValueError("Select at least one known plan result")
    chosen = [by_path[path] for path in selected]
    for row in chosen:
        if stop and stop():
            raise InterruptedError("Collection cancelled before copying")
        if harvester.sha256(row["path"]) != row["sha256"]:
            raise ValueError("Source changed since review: " + row["path"])
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Collection destination must be new")
    destination.mkdir(parents=True)
    result = harvester.export_files(chosen, plan["profile"], destination / "FILES", layout=layout, stop=stop, progress=progress)
    provenance = {"plan_sha256": plan["plan_sha256"], "topic": plan["topic"], "roots": plan["roots"],
                  "status": "complete" if all(row.get("exported_as") for row in result) else "partial_export",
                  "sources": chosen, "exports": result, "layout": layout, "exact_duplicate_groups": plan["exact_duplicate_groups"],
                  "note": "Copies only. No canonical winner selected. Relative links/assets have not been rewritten."}
    provenance["source_folders"] = sorted({str(Path(row["path"]).parent) for row in chosen})
    (destination / "PROVENANCE.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    (destination / "REVIEW.html").write_text(review_html(plan), encoding="utf-8")
    return provenance
