#!/usr/bin/env python3
"""Rename proposals for tagged papers, scored by FIS's prediction engines, into the FIS approval queue.

    python fis_propose.py --source <folder or file> [...]           show old name -> new name + engine scores
    python fis_propose.py --source <folder> --queue [--notify]      add them to the FIS approval queue (+ toast)

The new name is FIS's canonical grammar ({DOMAIN}_{TYPE}_{title-slug}_{YYYYMMDD}.ext, theophysics_taxonomy.py):
the domain from the paper's .fistag (run fistag.py --write first), the type from its title (Index -> MAP,
Derivation -> DRV, else PAP), the date from its 'DLowe YYYY-MM-DD' name (else the file's date).
Every proposal is scored by the preference ensemble (predict + each engine's vote), the same engines the approval
GUI learns into on every click. Nothing is renamed here: approving in the GUI only records the decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FIS = Path(r"D:\GitHub\David-OS\file-intelligence-system")
GUI = FIS / "approval-gui"
sys.path.insert(0, str(FIS))
sys.path.insert(0, str(FIS.parent / "engine"))
from theophysics_taxonomy import build_filename  # noqa: E402

OUTPUT_NAME = re.compile(r" · ([0-9]+_[A-Z0-9_]+|ANALYSIS|CKG|STORIES)\.md$")
STATUS = {"RUN": "DR", "RWK": "DR", "API": "RV", "CAN": "FN"}       # fistag stage -> FIS lifecycle status


def engine():
    try:
        from preference.ensemble import get_ensemble
        return get_ensemble()
    except Exception as e:  # the engines are optional; proposals still go in without scores
        print(f"(prediction engines not loaded: {e})")
        return None


def parts(path: Path) -> tuple[str, datetime, str]:
    """title, date, type from 'DLowe 2026-08-24 · CONSOLIDATED – 07 — TITLE · tags · Kind'."""
    bits = path.stem.split(" · ")
    m = re.match(r"\w+ (\d{4}-\d{2}-\d{2})$", bits[0]) if len(bits) > 1 else None
    date = datetime.strptime(m.group(1), "%Y-%m-%d") if m else datetime.fromtimestamp(path.stat().st_mtime)
    title = bits[1] if m else bits[0]
    title = re.sub(r"^(CONSOLIDATED|CANON|SOURCE|\s|[–—:\-_\d])+", "", title, flags=re.I)
    title = re.sub(r"^(CANON|SOURCE)\s+[\d\s–—\-_]*", "", title, flags=re.I).strip(" _-–—") or path.stem
    low = title.lower()
    kind = "MAP" if re.search(r"index|navigation|doorway|start here", low) else "DRV" if "derivation" in low else "PAP"
    return title, date, kind


def proposals(files: list[Path], eng) -> list[dict]:
    out = []
    for f in files:
        side = Path(str(f) + ".fistag")
        tag = json.loads(side.read_text(encoding="utf-8")) if side.is_file() else {}
        domain = tag.get("domain", "TPH")
        title, date, kind = parts(f)
        new = build_filename(domain, kind, title, date, f.suffix)
        status = STATUS.get(tag.get("stage", ""), "AC")
        tags = (tag.get("top_tags") or [])[:3]
        p = {"schema": "action_proposal.v1", "type": "rename", "id": "TAG-" + hashlib.sha1(str(f).encode()).hexdigest()[:12],
             "target": str(f), "path": str(f), "before": f.name, "after": new, "current_name": f.name, "proposed_name": new,
             "folder_class": f.parent.name, "domain": domain, "domain_code": domain, "ct": kind, "ct_code": kind,
             "status": status, "status_code": status, "tags": tags, "fistag": tag.get("fistag", ""),
             "confidence": 0.0, "rule_id": "tagger_fistag_v1", "ts": datetime.now().astimezone().isoformat(timespec="seconds")}
        if eng:
            try:
                p["engines"] = {k: round(v, 3) for k, v in eng.predict_breakdown(p).items()}
                p["predicted_approval"] = p["confidence"] = p["score"] = round(eng.predict(p), 3)
            except Exception as e:
                p["engines"] = {"error": str(e)[:120]}
        out.append(p)
    return out


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--source", action="append", required=True)
    a.add_argument("--queue", action="store_true", help="append to approval-gui/fis_proposals.jsonl")
    a.add_argument("--notify", action="store_true", help="raise the FIS toast (opens the approval page)")
    args = a.parse_args()
    files = []
    for s in map(Path, args.source):
        files += [s] if s.is_file() else sorted(f for f in s.rglob("*.md") if not OUTPUT_NAME.search(f.name)
                                                and not any(x.startswith(("_", ".")) for x in f.relative_to(s).parts[:-1]))
    rows = proposals(files, engine())
    for p in rows:
        votes = " ".join(f"{k}={v}" for k, v in (p.get("engines") or {}).items())
        print(f"{p.get('predicted_approval', '-'):>5}  {p['current_name'][:70]}\n       -> {p['proposed_name']}   [{p['fistag']}] {votes}")
    if args.queue:
        queue = GUI / "fis_proposals.jsonl"
        have = {json.loads(l).get("id") for l in queue.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()} if queue.exists() else set()
        new = [p for p in rows if p["id"] not in have]
        with queue.open("a", encoding="utf-8") as fh:
            for p in new:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"\nqueued {len(new)} new proposal(s) ({len(rows) - len(new)} already there) -> {queue}")
        if args.notify and new:
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GUI / "notify.ps1"),
                              "-Count", str(len(new))], creationflags=0x08000000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
