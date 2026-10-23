"""Aggregate everything known about a folder into one bundle, then render it.

``collect()`` runs the existing scanners (symptoms, references, quality) and joins
their output per file, stamping high-priority provenance from priority_roots.
``anomalies()`` reads the joined data for probable mistakes — the cases where two
signals disagree, which is where real errors hide. ``export()`` writes the bundle
as JSON, a flat CSV, and a dark visual report styled after the v3 vault viewer.

The JSON bundle is the handoff artifact: everything a model needs to write its own
version of the report, with no re-scanning.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import priority_roots, quality_score, reference_index
from .symptoms import run_all_symptoms

BACKUP_HINT = re.compile(r"(?:^|[\\/_.-])(bak|backup|backups|old|archive|copy|copies|zzz)(?:[\\/_.-]|$)", re.I)
VERSION_HINT = re.compile(r"[_\-. ]v(\d+)(?:\.(\d+))?|[_\-. ](\d+)$", re.I)
DEFAULT_EXPORT = Path.home() / "Documents" / "David-OS Reports"


# ── collection ────────────────────────────────────────────────────────────
def collect(root: str | Path, *, skip_dirs: tuple[str, ...] = priority_roots.DEFAULT_SKIP_NAMES) -> dict:
    base = Path(root).expanduser().resolve()
    roots = priority_roots.load()
    priority_roots.apply_write_protection(roots)

    report = run_all_symptoms(base)
    index = reference_index.build_index(base, skip_dirs=skip_dirs)
    quality = quality_score.snapshot(base, skip_dirs=skip_dirs)

    findings = defaultdict(list)
    for result in report.results:
        findings[str(result.path)].append({"code": result.symptom_id, "name": result.name,
                                           "severity": result.severity.value, "message": result.message,
                                           "evidence": result.evidence})

    scores = {s["path"]: s for s in quality["scores"]}
    incoming = {path: len(refs) for path, refs in index.incoming.items()}

    files = []
    for path in sorted(set(findings) | set(scores) | {str(p) for p in index.incoming}):
        stamp = priority_roots.provenance(path, roots)
        score = scores.get(path, {})
        files.append({
            "path": path,
            "name": Path(path).name,
            "folder": str(Path(path).parent),
            "exists": Path(path).exists(),
            "bytes": Path(path).stat().st_size if Path(path).exists() and Path(path).is_file() else None,
            "findings": findings.get(path, []),
            "quality": {k: score.get(k) for k in ("score", "grade", "words", "reasons")} if score else None,
            "referenced_by": incoming.get(Path(path), 0),
            "in_backup_path": bool(BACKUP_HINT.search(path)),
            **stamp,
        })

    bundle = {
        "schema": "david-os/aggregate-report/1",
        "root": str(base),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "priority_roots": [r.to_dict() for r in roots],
        "totals": _totals(files, report, index, quality),
        "symptoms": report.to_dict(),
        "references": {"files_scanned": index.to_dict()["files_scanned"],
                       "targets": index.to_dict()["targets"],
                       "broken": index.to_dict()["broken"]},
        "quality": {k: quality[k] for k in ("files", "mean_score", "median_score", "grades")},
        "files": files,
    }
    bundle["anomalies"] = anomalies(bundle)
    return bundle


def _totals(files: list[dict], report, index, quality) -> dict:
    scored = [f["quality"]["score"] for f in files if f.get("quality") and f["quality"].get("score") is not None]
    return {
        "files_with_signal": len(files),
        "findings": report.count,
        "by_severity": report.by_severity,
        "broken_references": len(index.broken),
        "high_priority_files": sum(1 for f in files if f["high_priority"]),
        "files_scored": quality["files"],
        "mean_quality": round(statistics.mean(scored), 1) if scored else 0.0,
        "thin_files": sum(1 for f in files for x in f["findings"] if x["code"] == "C09"),
        "duplicate_clusters": sum(1 for x in report.results if x.symptom_id == "C01"),
    }


# ── probable mistakes ─────────────────────────────────────────────────────
def anomalies(bundle: dict) -> list[dict]:
    """Where two signals disagree. Ranked: these are the rows to read first."""
    out: list[dict] = []
    files = {f["path"]: f for f in bundle["files"]}

    def add(kind: str, severity: str, path: str, why: str, **extra) -> None:
        out.append({"kind": kind, "severity": severity, "path": path, "why": why, **extra})

    for path, f in files.items():
        q = f.get("quality") or {}
        score, refs = q.get("score"), f.get("referenced_by", 0)

        if f["in_backup_path"] and refs > 0:
            add("live_file_in_backup", "critical", path,
                f"{refs} page(s) link to a file sitting in a backup folder — the backup is load-bearing.",
                referenced_by=refs)
        if score is not None and score >= 80 and refs == 0 and not f["in_backup_path"]:
            add("orphan_good_page", "high", path,
                f"scores {score} but nothing links to it — finished work that is unreachable.", score=score)
        if score is not None and score < 45 and refs >= 3:
            add("weak_page_load_bearing", "high", path,
                f"scores {score} but {refs} page(s) depend on it.", score=score, referenced_by=refs)
        if f["high_priority"] and f["findings"]:
            add("finding_in_priority_place", "high", path,
                f"{len(f['findings'])} finding(s) inside high-priority root {f['priority_root']}.",
                priority_root=f["priority_root"], label=f["priority_label"])
        if any(x["code"] == "C09" for x in f["findings"]) and refs > 0:
            add("thin_but_linked", "medium", path,
                f"near-empty yet linked from {refs} place(s) — a stub is standing in for real content.",
                referenced_by=refs)

    # duplicate clusters whose members straddle a backup boundary, or a priority root
    for result in bundle["symptoms"]["results"]:
        if result["symptom_id"] != "C01":
            continue
        members = [str(m) for m in result.get("evidence", {}).get("files", [])]
        live = [m for m in members if not BACKUP_HINT.search(m)]
        if len(members) > 1 and not live:
            add("all_copies_in_backup", "medium", members[0],
                f"{len(members)} identical copies and every one is in a backup path.", files=members)
        elif len(live) > 1:
            add("duplicate_live_copies", "high", live[0],
                f"{len(live)} identical live copies outside backups — unclear which is canonical.", files=live)
        if any(priority_roots.is_high_priority(m) for m in members) and len(members) > 1:
            add("duplicate_crosses_priority", "high", members[0],
                "a duplicate cluster spans a high-priority root.", files=members)

    # version families where the highest number is not the newest file
    families: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for path in files:
        stem = Path(path).stem
        match = VERSION_HINT.search(stem)
        if not match:
            continue
        number = next((int(g) for g in match.groups() if g and g.isdigit()), None)
        if number is None:
            continue
        families[(str(Path(path).parent), VERSION_HINT.sub("", stem).lower())].append((number, path))
    for (folder, base_name), members in families.items():
        if len(members) < 2:
            continue
        try:
            newest = max(members, key=lambda m: Path(m[1]).stat().st_mtime)
        except OSError:
            continue
        highest = max(members, key=lambda m: m[0])
        if newest[1] != highest[1]:
            add("version_order_mismatch", "medium", newest[1],
                f"'{base_name}' — newest file is v{newest[0]} but v{highest[0]} exists; "
                "the highest version number is not the latest edit.",
                folder=folder, members=[m[1] for m in members])

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    out.sort(key=lambda a: (rank.get(a["severity"], 4), a["kind"], a["path"]))
    return out


# ── export ────────────────────────────────────────────────────────────────
def export(bundle: dict, out_dir: str | Path | None = None, *, name: str = "") -> dict[str, str]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = name or Path(bundle["root"]).name or "scan"
    target = Path(out_dir or DEFAULT_EXPORT) / f"{label}_{stamp}"
    target.mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}
    bundle_path = target / "bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    written["bundle"] = str(bundle_path)

    anomaly_path = target / "anomalies.csv"
    with anomaly_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["severity", "kind", "path", "why"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(bundle["anomalies"])
    written["anomalies"] = str(anomaly_path)

    files_path = target / "files.csv"
    with files_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "bytes", "quality_score", "grade", "words", "referenced_by",
                         "findings", "high_priority", "priority_root", "in_backup_path"])
        for f in bundle["files"]:
            q = f.get("quality") or {}
            writer.writerow([f["path"], f["bytes"], q.get("score"), q.get("grade"), q.get("words"),
                             f["referenced_by"], len(f["findings"]), f["high_priority"],
                             f["priority_root"] or "", f["in_backup_path"]])
    written["files"] = str(files_path)

    html_path = target / "report.html"
    html_path.write_text(render_html(bundle), encoding="utf-8")
    written["html"] = str(html_path)

    prompt_path = target / "HANDOFF_PROMPT.md"
    prompt_path.write_text(handoff_prompt(bundle), encoding="utf-8")
    written["handoff"] = str(prompt_path)
    written["folder"] = str(target)
    return written


def handoff_prompt(bundle: dict) -> str:
    totals = bundle["totals"]
    return f"""# Folder intelligence handoff — {bundle['root']}

Generated {bundle['generated']} by David-OS v3 `engine/aggregate_report.py`.

`bundle.json` holds every signal collected; `anomalies.csv` and `files.csv` are flat views
of the same data. Nothing was changed on disk — this is a read-only observation.

## What the numbers are
- {totals['files_with_signal']} files carry at least one signal; {totals['files_scored']} were scored for writing quality (mean {totals['mean_quality']}).
- {totals['findings']} folder-health findings, by severity: {totals['by_severity']}.
- {totals['broken_references']} broken references, {totals['duplicate_clusters']} duplicate clusters, {totals['thin_files']} empty or near-empty files.
- {totals['high_priority_files']} files sit inside a declared high-priority root.
- {len(bundle['anomalies'])} probable mistakes (cases where two signals disagree).

## Field guide
- `files[].quality.score` — 0-100 structural writing score, with `reasons` naming each deduction.
- `files[].referenced_by` — how many pages link to this file.
- `files[].in_backup_path` — the path itself looks like a backup location.
- `files[].high_priority` / `priority_root` — provenance from the declared priority list.
- `anomalies[].kind` — the disagreement found; see `why` for the plain-English reason.

## The task
Write the clearest possible report for the folder's owner. Lead with probable mistakes and
anomalies, then the structural picture, then what to do in what order. Be specific: name files,
give counts, and say what is at risk. Do not recommend deleting anything — non-canonical
versions are archived, never removed. Flag anything in the data that looks self-contradictory.
"""


# ── visual report (styled after fis_vault_intelligence_v3) ────────────────
def _esc(value: object) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_html(bundle: dict) -> str:
    totals = bundle["totals"]
    anomaly_rows = "\n".join(
        f'<tr class="sev-{_esc(a["severity"])}"><td><span class="badge {_esc(a["severity"])}">{_esc(a["severity"])}</span></td>'
        f'<td><code>{_esc(a["kind"])}</code></td><td class="path">{_esc(a["path"])}</td><td>{_esc(a["why"])}</td></tr>'
        for a in bundle["anomalies"]) or '<tr><td colspan="4" class="muted">No disagreements found.</td></tr>'

    worst = sorted((f for f in bundle["files"] if f.get("quality") and f["quality"].get("score") is not None),
                   key=lambda f: f["quality"]["score"])[:60]
    worst_rows = "\n".join(
        f'<tr><td class="scorecell">{f["quality"]["score"]}</td><td><span class="badge g{_esc(f["quality"]["grade"])}">'
        f'{_esc(f["quality"]["grade"])}</span></td><td class="path">{_esc(f["path"])}</td>'
        f'<td>{f["quality"].get("words") or 0}</td><td>{f["referenced_by"]}</td>'
        f'<td class="muted">{_esc("; ".join(f["quality"].get("reasons") or []))}</td></tr>' for f in worst)

    counts: dict[str, int] = defaultdict(int)
    for result in bundle["symptoms"]["results"]:
        counts[f'{result["symptom_id"]} {result["name"]}'] += 1
    symptom_rows = "\n".join(
        f'<tr><td><code>{_esc(code)}</code></td><td>{count}</td></tr>'
        for code, count in sorted(counts.items(), key=lambda kv: -kv[1]))

    broken_rows = "\n".join(
        f'<tr><td class="path">{_esc(b["from"])}</td><td><code>{_esc(b["ref"])}</code></td></tr>'
        for b in bundle["references"]["broken"][:300]) or '<tr><td colspan="2" class="muted">None.</td></tr>'

    priority_rows = "\n".join(
        f'<tr><td><span class="badge {"gated" if r["mode"] == "skip" else "working"}">{_esc(r["mode"])}</span></td>'
        f'<td class="path">{_esc(r["path"])}</td><td>{_esc(r["label"])}</td><td class="muted">{_esc(r["note"])}</td></tr>'
        for r in bundle["priority_roots"]) or '<tr><td colspan="4" class="muted">No high-priority roots declared.</td></tr>'

    grades = " ".join(f'<span class="badge g{_esc(g)}">{_esc(g)} {n}</span>'
                      for g, n in (bundle["quality"].get("grades") or {}).items())

    return f"""<!doctype html>
<html lang="en" data-fis-schema="3.0"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="David-OS v3 aggregate_report">
<title>Folder Intelligence — {_esc(Path(bundle['root']).name)}</title>
<style>
:root{{color-scheme:dark;--bg:#060708;--panel:#0c0f14;--panel2:#090b0f;--line:#222a35;--text:#e7edf5;
--muted:#8b97a7;--accent:#d1a922;--accent2:#f1d37a;--link:#6ea8e8;--red:#b0413e;--green:#5f9e6a;--blue:#4a7fb5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}}
.wrap{{max-width:1500px;margin:auto;padding:24px 28px}}
h1{{font:600 30px Georgia,serif;margin:4px 0 6px}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:1px;color:var(--accent);margin:30px 0 10px}}
.eyebrow,code{{font-family:ui-monospace,Consolas,monospace}}
.eyebrow{{color:var(--accent);font-size:12px;letter-spacing:1px}}.muted{{color:var(--muted)}}
.cards{{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}}
.card{{border:1px solid var(--line);background:var(--panel);padding:12px 16px;min-width:150px}}
.card .n{{font:600 26px Georgia,serif;color:var(--accent2)}}.card .l{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}}
table{{width:100%;border-collapse:collapse;background:var(--panel);margin-bottom:8px}}
th,td{{border:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}}
th{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}}
tr:hover td{{background:#10141b}}.path{{font-family:ui-monospace,Consolas,monospace;font-size:12px;word-break:break-all}}
.badge{{display:inline-block;border:1px solid var(--line);padding:1px 7px;border-radius:3px;font:11px ui-monospace,monospace;white-space:nowrap}}
.badge.critical{{border-color:var(--red);background:var(--red);color:#fff}}.badge.high{{border-color:var(--red);color:#ffb3b1}}
.badge.medium{{border-color:var(--accent);color:var(--accent2)}}.badge.low{{border-color:var(--line);color:var(--muted)}}
.badge.gated{{border-color:var(--red);color:#ffb3b1}}.badge.working{{border-color:var(--accent);color:var(--accent2)}}
.badge.gA{{border-color:var(--green);color:var(--green)}}.badge.gB{{border-color:#7ba05b;color:#7ba05b}}
.badge.gC{{border-color:var(--accent);color:var(--accent2)}}.badge.gD{{border-color:#b5854a;color:#b5854a}}
.badge.gF{{border-color:var(--red);color:#ffb3b1}}
.scorecell{{font:600 15px Georgia,serif;color:var(--accent2);width:56px}}
details{{border:1px solid var(--line);background:var(--panel2);padding:10px 12px;margin-bottom:10px}}
summary{{cursor:pointer;color:var(--accent)}}
.note{{border-left:3px solid var(--accent);padding:8px 12px;background:var(--panel2);margin:12px 0;color:var(--muted)}}
</style></head><body><div class="wrap">
<div class="eyebrow">DAVID-OS V3 · FOLDER INTELLIGENCE · READ-ONLY</div>
<h1>{_esc(bundle['root'])}</h1>
<div class="muted">Generated {_esc(bundle['generated'])} · {totals['files_with_signal']} files carry a signal ·
quality mean {totals['mean_quality']} {grades}</div>

<div class="cards">
  <div class="card"><div class="n">{len(bundle['anomalies'])}</div><div class="l">Probable mistakes</div></div>
  <div class="card"><div class="n">{totals['findings']}</div><div class="l">Health findings</div></div>
  <div class="card"><div class="n">{totals['broken_references']}</div><div class="l">Broken links</div></div>
  <div class="card"><div class="n">{totals['duplicate_clusters']}</div><div class="l">Duplicate clusters</div></div>
  <div class="card"><div class="n">{totals['thin_files']}</div><div class="l">Empty / near-empty</div></div>
  <div class="card"><div class="n">{totals['high_priority_files']}</div><div class="l">In priority roots</div></div>
</div>

<div class="note">Read this section first. Each row is a place where two independent signals disagree —
a page that scores well but nothing links to, a stub that other pages depend on, a backup folder that
turns out to be load-bearing. Disagreements are where real mistakes live.</div>

<h2>Probable mistakes &amp; anomalies</h2>
<table><thead><tr><th>Severity</th><th>Kind</th><th>Path</th><th>Why it matters</th></tr></thead>
<tbody>{anomaly_rows}</tbody></table>

<h2>High-priority roots</h2>
<table><thead><tr><th>Mode</th><th>Path</th><th>Label</th><th>Note</th></tr></thead>
<tbody>{priority_rows}</tbody></table>

<h2>Weakest writing — sorted worst first</h2>
<table><thead><tr><th>Score</th><th>Grade</th><th>Path</th><th>Words</th><th>Links in</th><th>Why marked down</th></tr></thead>
<tbody>{worst_rows}</tbody></table>

<h2>Folder health by symptom</h2>
<details open><summary>{len(counts)} symptom types</summary>
<table><thead><tr><th>Symptom</th><th>Count</th></tr></thead><tbody>{symptom_rows}</tbody></table></details>

<h2>Broken references</h2>
<details><summary>{totals['broken_references']} broken links (first 300 shown)</summary>
<table><thead><tr><th>In file</th><th>Points at</th></tr></thead><tbody>{broken_rows}</tbody></table></details>

<div class="note">Nothing on disk was changed to produce this report. `bundle.json` in this folder holds
every signal behind it, and `HANDOFF_PROMPT.md` is written for handing that bundle to another model.</div>
</div></body></html>"""


def run(root: str | Path, out_dir: str | Path | None = None, *, name: str = "") -> dict[str, str]:
    """Collect, detect, export. One call for the GUI button and the CLI alike."""
    bundle = collect(root)
    written = export(bundle, out_dir, name=name)
    written["anomaly_count"] = str(len(bundle["anomalies"]))
    return written
