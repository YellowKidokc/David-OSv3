"""Sidecar report — writes docs/SIDECAR_CLASSIFICATIONS.md (and a .html copy) from the live cards, so the
classifications can be read in one place instead of 52 tiny files.

    python sidecar_report.py                       (AXIOM canon sidecars)
    python sidecar_report.py "<folder>\\sidecars"

Re-run after any change; the doc is generated, never edited by hand.
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "00_SHARED"))   # taxonomy_validator
sys.path.insert(0, os.environ.get("PREDICTION_GUI", str(HERE.parent / "02_CLASSIFICATION")))  # harness

from taxonomy_validator import validate_sidecar_card            # noqa: E402
from harness.adapters.sidecars import parse_card                # noqa: E402

DEFAULT = "//192.168.2.50/h_hp/Desktop/Folders/AXIOM_CLASSIFICATION_CANON_2026-07-25 (1)/sidecars"
ORDER = ["canon", "declaration", "freeze-candidate", "proposed", "draft",
         "reference", "superseded", "inert"]
MEANING = {
    "canon": "human-ruled canonical",
    "declaration": "fixes something the framework treats as given",
    "freeze-candidate": "proposed for freeze, awaiting ruling",
    "proposed": "put forward, not yet ruled",
    "draft": "work in progress",
    "reference": "lookup material, no claims of its own",
    "superseded": "replaced by a newer source",
    "inert": "dead duplicate",
}

# Cards where DeepSeek, blind to the current value, read the summary differently
# (2026-10-13 run). Suggestions only — rule on them in REVIEW.bat.
FLAGS = {
    "Truth Kernel 001-100": ("draft", "summary says 'First-pass classification'"),
    "Truth Kernel 101-188": ("draft", "summary says 'First-pass classification'"),
    "Trinity First Pass": ("draft", "a first-pass report; 'low process agreement', 'PARTIAL mirror gate'"),
    "Framework Mapping": ("reference", "'master list mapping every axiom ID' — a lookup list"),
    "Why Math Works": ("draft or proposed", "summary says the argument 'remains WHY_UNFINISHED'"),
    "AI Reading Order": ("draft", "'working runway … without freezing the story'"),
    "First Principles Rebuild": ("proposed", "summary says 'pending a ruling'"),
}


def summary_of(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").replace("\r", "").split("\n")
    body, seen_fm, in_fm = [], 0, False
    for l in lines:
        if l.strip() == "---" and seen_fm < 2:
            seen_fm += 1; continue
        if seen_fm >= 2 and l.strip() and not l.startswith("# ") and not l.startswith("Read [["):
            body.append(l.strip())
    return " ".join(body)


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<i>\1</i>", s)


def to_html(lines: list[str], title: str) -> str:
    """Just enough Markdown for this report: headings, quotes, lists, tables, rules."""
    out, table = [], False
    for l in lines:
        if l.startswith("|"):
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", l.strip())[1:-1]]
            if all(re.fullmatch(r"-+", c) for c in cells):
                continue
            tag = "td" if table else "th"
            out.append(("" if table else "<table>") + "<tr>" +
                       "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
            table = True
            continue
        if table:
            out.append("</table>"); table = False
        if l.startswith("#"):
            n = len(l) - len(l.lstrip("#"))
            out.append(f"<h{n}>{_inline(l[n:].strip())}</h{n}>")
        elif l.startswith(">"):
            out.append(f"<blockquote>{_inline(l[1:].strip())}</blockquote>")
        elif l.startswith("- "):
            out.append(f"<li>{_inline(l[2:])}</li>")
        elif l.strip() == "---":
            out.append("<hr>")
        elif l.strip():
            out.append(f"<p>{_inline(l)}</p>")
    if table:
        out.append("</table>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><style>
:root{{--bg:#fff;--fg:#1d1d1f;--mute:#6b6b70;--line:#e3e3e8;--head:#f5f5f7;--code:#f0f0f3}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161618;--fg:#ececf0;--mute:#9a9aa2;--line:#2e2e33;--head:#1f1f23;--code:#26262b}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif;max-width:1100px;margin:0 auto;padding:24px 16px}}
table{{border-collapse:collapse;width:100%;margin:8px 0 24px;font-size:14px}}
th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:var(--head);position:sticky;top:0}}
code{{background:var(--code);padding:1px 4px;border-radius:4px;font-size:12px;word-break:break-all}}
blockquote{{margin:4px 0;padding:6px 12px;border-left:3px solid var(--line);color:var(--mute)}}
h2{{margin-top:32px}}
</style></head><body>
{chr(10).join(out)}
</body></html>
"""


def main(folder: Path) -> Path:
    rows, broken = [], []
    for p in sorted(folder.glob("*.md")):
        fields, tags = parse_card(p)
        if not fields:
            if "subject-index" not in p.read_text(encoding="utf-8", errors="replace")[:400]:
                broken.append(p.name)
            continue
        rows.append({
            "subject": fields.get("subject", p.stem),
            "standing": fields.get("standing", ""),
            "version": fields.get("version", ""),
            "source": fields.get("source_file", ""),
            "domain": fields.get("domain", ""),
            "tags": [t for t in tags if t not in ("sidecar", "subject")],
            "summary": summary_of(p),
            "problems": validate_sidecar_card(p),
        })
    counts = Counter(r["standing"] for r in rows)
    tagged = sum(1 for r in rows if r["tags"])
    out = [
        "# Sidecar Classifications",
        "",
        f"*Generated {dt.datetime.now():%Y-%m-%d %H:%M} by `sidecar_report.py` from `{folder}` — do not edit; re-run.*",
        "",
        f"**{len(rows)} cards** · " + " · ".join(f"{counts[s]} {s}" for s in ORDER if counts[s])
        + f" · **{tagged} of {len(rows)} carry Part A tags** (ct-/ep-/topic)"
        + (f" · {sum(1 for r in rows if r['problems'])} fail validation" if any(r["problems"] for r in rows) else " · all pass validation"),
        "",
        "Each card is a pointer to one source paper: a short name, a standing (how settled it is),",
        "and one sentence on what the paper does. Rules: `00_SHARED/TAG_TAXONOMY_v0.4.md` Part B.",
        "",
    ]
    if tagged == 0:
        out += ["> **Not tagged yet.** No card has `ct-` / `ep-` / topic tags. That is step 3 (Tag),",
                "> which needs the source papers — their location is currently unknown.", ""]
    flagged = [r for r in rows if r["subject"] in FLAGS and FLAGS[r["subject"]][0].split()[0] != r["standing"]]
    if flagged:
        out += ["## Worth a second look", "",
                "DeepSeek, reading only the name and summary with the current standing hidden, saw these differently.",
                "Suggestions only — decide in `REVIEW.bat` (filter *Disagrees with current*).", "",
                "| Card | Card says | DeepSeek reads | Why |", "|---|---|---|---|"]
        out += [f"| {cell(r['subject'])} | {r['standing']} | {FLAGS[r['subject']][0]} | {cell(FLAGS[r['subject']][1])} |"
                for r in flagged]
        out.append("")
    for st in ORDER + sorted(set(counts) - set(ORDER)):
        group = sorted((r for r in rows if r["standing"] == st), key=lambda r: r["subject"].lower())
        if not group:
            continue
        out += [f"## {st} ({len(group)}) — {MEANING.get(st, 'not in the closed list')}", "",
                "| Card | Ver | What the paper does | Source file |", "|---|---|---|---|"]
        for r in group:
            name = cell(r["subject"]) + (" ⚠" if r["problems"] else "") + (" 🔎" if r["subject"] in FLAGS else "")
            out.append(f"| {name} | {r['version']} | {cell(r['summary'])} | `{cell(r['source'])}` |")
        out.append("")
    if broken:
        out += ["## Unreadable", ""] + [f"- `{b}`" for b in broken] + [""]
    out += ["---", "⚠ fails validation · 🔎 flagged above"]
    dst = HERE / "docs" / "SIDECAR_CLASSIFICATIONS.md"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    dst.with_suffix(".html").write_text(to_html(out, "Sidecar classifications"), encoding="utf-8")
    return dst


if __name__ == "__main__":
    print(main(Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)))
