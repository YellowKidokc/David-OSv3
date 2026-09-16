"""Printout of Cross-Domain Coherence Project for Kimi: lossless proposals, twins, symptoms."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fis_namer import propose_lossless_address, propose_name

ROOT = Path(r"\\192.168.2.50\h_hp\Desktop\Cross-Domain Coherence Project")
OUT = ROOT / "KIMI_FIS_REVIEW_PACKET.md"
OUT2 = HERE / "reports" / "KIMI_CDC_REVIEW_PACKET.md"

SKIP_DIR = {".venv-convert", ".git", "node_modules", "__pycache__", "$recycle.bin", ".obsidian"}
SPINE = {
    "00_canonical_theophysics_synthesis",
    "01_federal_reserve",
    "02_psychology_crisis",
    "03_education",
    "04_scientific_method",
    "05_theological_engineering",
    "07_semantic_entropy",
    "08_coherence_tools",
    "09_jesus_series",
    "10_trinity",
    "11_master_equation",
    "12_demographics",
    "13_architecture",
    "14_ai_synthesis_final",
}
TWIN = {
    "education": "03_education",
    "psychology": "02_psychology_crisis",
    "psychology_crisis": "02_psychology_crisis",
    "trinity": "10_trinity",
    "federal reserve": "01_federal_reserve",
    "semantic_entropy": "07_semantic_entropy",
    "scientific method": "04_scientific_method",
    "master eq": "11_master_equation",
    "theological_engineering": "05_theological_engineering",
}


def sample_text(path: Path, n: int = 1800) -> str:
    if path.suffix.lower() not in {".md", ".txt", ".html", ".htm"}:
        return ""
    try:
        if path.stat().st_size > 1_500_000:
            return f"[large {path.stat().st_size} bytes]"
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(n)
    except OSError:
        return ""


def main() -> int:
    if not ROOT.is_dir():
        print("missing", ROOT)
        return 1
    files: list[dict] = []
    untitled: list[dict] = []
    stragglers: list[dict] = []
    by_stem: dict[str, list[str]] = defaultdict(list)
    print("walking...", flush=True)
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIR]
        parent = Path(dirpath)
        for name in filenames:
            path = parent / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            rel = str(path.relative_to(ROOT))
            stem_key = re.sub(r"[\s_\-]+", " ", Path(name).stem.lower())
            by_stem[stem_key].append(rel)
            rec = {
                "rel": rel,
                "name": name,
                "bytes": size,
                "parent": parent.name,
            }
            files.append(rec)
            low = name.lower()
            interesting = (
                low.startswith("untitled")
                or "new folder" in low
                or "i think we need" in low
                or parent == ROOT
            )
            if interesting:
                text = sample_text(path)
                rec["lossless"] = propose_lossless_address(path.stem, text, path.stat().st_mtime).get("address")
                proposal = propose_name({
                    "name": name,
                    "path": str(path),
                    "ext": path.suffix.lower(),
                    "mtime": path.stat().st_mtime,
                    "chi_domain": "",
                    "content_type": "document",
                    "chi_confidence": 0.4,
                    "sample": text[:800],
                })
                rec["proposed"] = proposal.get("proposed_name") or ""
                rec["decision"] = proposal.get("decision") or ""
                if parent == ROOT and path.suffix:
                    stragglers.append(rec)
                if low.startswith("untitled") or "new folder" in low or "i think we need" in low:
                    untitled.append(rec)
            if len(files) % 200 == 0:
                print(f"  {len(files)} files", flush=True)

    root_dirs = [p.name for p in ROOT.iterdir() if p.is_dir() and p.name.lower() not in SKIP_DIR]
    off_spine = []
    for name in sorted(root_dirs):
        key = name.lower().replace(" ", "_")
        numbered = bool(re.match(r"^\d{2}_", name))
        if numbered or name.startswith("_"):
            continue
        twin = TWIN.get(name.lower()) or TWIN.get(key)
        off_spine.append((name, twin))

    lines = [
        "# Kimi review packet — Cross-Domain Coherence Project",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Root: `{ROOT}`",
        f"Files listed: **{len(files)}** (skipped `.venv-convert` / `.git` / node_modules)",
        "",
        "## What we want from you",
        "Propose **file actions** for FIS.html (promote-to-spine, quarantine, flag-review, mark-duplicate, ignore).",
        "Map each cluster to `folder_symptom_registry.xlsx` IDs (N01, S02, C01, C02, R01, GR-003…) where they fit.",
        "Do not recommend silent deletes. Quarantine / `_NON_CANONICAL_REVIEW` / numbered spine only.",
        "Lossless addresses below are **proposals**. Nothing was renamed.",
        "",
        "## Off-spine root folders (likely twins / archive / tooling)",
        "",
        "| Folder | Twin of numbered spine |",
        "|---|---|",
    ]
    for name, twin in off_spine:
        lines.append(f"| `{name}` | `{twin or 'none / review'}` |")

    lines += [
        "",
        "## Untitled + broken names",
        "",
        "| Current | Bytes | Lossless address | Proposed filename | Namer decision |",
        "|---|---:|---|---|---|",
    ]
    for rec in sorted(untitled, key=lambda r: r["name"].lower()):
        lines.append(
            f"| `{rec['name']}` | {rec['bytes']:,} | `{rec.get('lossless','')}` | `{rec.get('proposed','')}` | {rec.get('decision','')} |"
        )

    lines += [
        "",
        "## Root stragglers",
        "",
        "| File | Bytes | Lossless | Proposed |",
        "|---|---:|---|---|",
    ]
    for rec in sorted(stragglers, key=lambda r: -r["bytes"])[:100]:
        lines.append(
            f"| `{rec['name']}` | {rec['bytes']:,} | `{rec.get('lossless','')}` | `{rec.get('proposed','')}` |"
        )

    lines += [
        "",
        "## Same-stem clusters (name closeness only — not proven identity)",
        "",
    ]
    shown = 0
    for stem, rows in sorted(by_stem.items(), key=lambda kv: -len(kv[1])):
        if shown >= 35 or len(set(Path(r).name for r in rows)) < 2:
            continue
        if len(rows) < 2:
            continue
        lines.append(f"### `{stem}` ({len(rows)} files)")
        for rel in rows[:12]:
            lines.append(f"- `{rel}`")
        shown += 1

    lines += [
        "",
        "## Symptoms that should fire",
        "",
        "- N01 name rot — Untitled*, New folder, broken HTML filename",
        "- S02 / SYM-012 version sprawl — numbered spine vs unnumbered domain folders",
        "- C02 format redundancy — md/html pairs in same-stem clusters",
        "- SYM-008 archive pile — Archive / A3_ARCHIVE / migration archive",
        "- GR-003 protect — do not auto-move `.venv-convert`",
        "- R01 untagged canonical — Claudian audit: no scoring",
        "",
        "## Full file list (relative path + bytes)",
        "",
        "| Bytes | Path |",
        "|---:|---|",
    ]
    for rec in sorted(files, key=lambda r: r["rel"].lower()):
        lines.append(f"| {rec['bytes']:,} | `{rec['rel']}` |")

    lines += [
        "",
        "```json",
        json.dumps({"untitled": untitled, "root_stragglers": stragglers[:60], "off_spine": off_spine}, indent=2)[:20000],
        "```",
        "",
    ]
    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")
    OUT2.parent.mkdir(parents=True, exist_ok=True)
    OUT2.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"wrote {OUT2}")
    print(f"files={len(files)} untitled={len(untitled)} root_stragglers={len(stragglers)} off_spine={len(off_spine)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
