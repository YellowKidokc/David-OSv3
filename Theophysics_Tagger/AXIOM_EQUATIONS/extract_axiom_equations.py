"""Pull every equation out of the 191 AXIOM production nodes (plus the matching
legacy sequential record's Formal Expression) into one Excel workbook and one
long Markdown paper. Read-only on the source folders."""
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SRC = Path(r"C:\Users\David\Documents\faiththruphysics.com\Canon\AXIOM\LIVE"
           r"\10_VAULTS~00_ Production~21_AXIOM NODES")
LEGACY = SRC / "90_LEGACY_SEQUENTIAL_PROJECTIONS__0001_TO_0009"
OUT = Path(__file__).parent


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm


def section(text, heading_regex):
    m = re.search(rf"^##\s+{heading_regex}.*?$\n(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    if not m:
        return ""
    body = re.split(r"^---\s*$|^%%", m.group(1), flags=re.M)[0]
    return body.strip()


def unquote(text):
    return "\n".join(re.sub(r"^\s*>\s?", "", l) for l in text.splitlines())


def production_equations(body):
    """Return list of (block_label, latex, word_eq, plain_english)."""
    lines = unquote(body).splitlines()
    eqs, label, i = [], "Formal Articulation", 0
    pending = []  # equations in current callout awaiting word/plain notes
    word = plain = ""
    while i < len(lines):
        line = lines[i]
        cm = re.match(r"\[!(\w+)\]\s*(.*)", line.strip())
        hm = re.match(r"#{2,4}\s+(.*)", line.strip())
        if cm or hm:
            if pending:
                pending[-1][2], pending[-1][3] = word, plain
            pending, word, plain = [], "", ""
            label = (cm.group(2) or cm.group(1)) if cm else hm.group(1)
        s = line.strip()
        if s.startswith("$$"):
            buf = s[2:]
            if buf.endswith("$$") and len(buf) >= 2:
                latex = buf[:-2]
            else:
                parts = [buf]
                i += 1
                while i < len(lines) and "$$" not in lines[i]:
                    parts.append(lines[i])
                    i += 1
                if i < len(lines):
                    parts.append(lines[i].split("$$")[0])
                latex = "\n".join(parts)
            latex = latex.strip()
            if latex:
                e = [label.strip(), latex, "", ""]
                eqs.append(e)
                pending.append(e)
        wm = re.match(r"\*\*Word equation:\*\*\s*(.*)", s)
        pm = re.match(r"\*\*Plain English:\*\*\s*(.*)", s)
        if wm:
            word = wm.group(1)
        if pm:
            plain = pm.group(1)
        i += 1
    if pending:
        pending[-1][2], pending[-1][3] = word, plain
    return [tuple(e) for e in eqs]


def where_glossary(body):
    m = re.search(r"^Where:\s*\n((?:\s*-\s.*\n?)+)", body, re.M)
    return "\n".join(l.strip()[2:] for l in m.group(1).splitlines() if l.strip()) if m else ""


def first_statement(sec1):
    for para in re.split(r"\n\s*\n", sec1):
        p = para.strip()
        if p and not p.startswith(">") and not p.startswith("---") and not p.startswith("$$"):
            return p
    return ""


def legacy_record(pos):
    hits = sorted(LEGACY.glob(f"{pos:04d}_*.md"))
    if not hits:
        return None
    t = hits[0].read_text(encoding="utf-8", errors="replace")
    fe = section(t, r"Formal Expression")
    code = re.findall(r"```[^\n]*\n(.*?)```", fe, re.S)
    formal = "\n".join(c.strip() for c in code) if code else fe
    lim = section(t, r"Limitations")
    cid = re.search(r"\|\s*Canonical ID\s*\|\s*`([^`]+)`", t)
    return {
        "file": hits[0].name,
        "id": cid.group(1) if cid else "",
        "formal": formal.strip(),
        "statement": section(t, r"Statement"),
        "mdp": section(t, r"Maximum Defensible Position"),
        "limitations": lim,
        "refs": section(t, r"References"),
    }


def kill_condition(text):
    m = re.search(r"\*\*Kill Condition:\*\*\s*(.*)", text)
    return m.group(1).strip() if m else ""


nodes = []
for f in sorted(SRC.glob("[0-9][0-9][0-9]_*.md")):
    pos = int(f.name[:3])
    t = f.read_text(encoding="utf-8", errors="replace")
    fm = frontmatter(t)
    sec1 = section(t, r"1\.")
    leg = legacy_record(pos)
    nodes.append({
        "pos": pos, "file": f.name,
        "id": fm.get("canonical_id", ""), "label": fm.get("human_label", ""),
        "mode": fm.get("mode", ""), "status": fm.get("status", ""), "tier": fm.get("tier", ""),
        "statement": first_statement(sec1),
        "eqs": production_equations(sec1),
        "where": where_glossary(sec1),
        "kill": kill_condition(t),
        "legacy": leg,
    })

if len(nodes) != 191:
    print(f"WARNING: expected 191 nodes, found {len(nodes)}", file=sys.stderr)

# ---------------- Excel ----------------
wb = Workbook()
ws = wb.active
ws.title = "Equations"
hdr = ["Eq #", "Pos", "Node ID", "Node name", "Mode", "Status", "Source", "Block",
       "Equation", "Word equation", "Plain English", "Verdict (OK / WRONG / ?)", "Notes"]
ws.append(hdr)
n = 0
for nd in nodes:
    rows = [("Production node", b, l, w, p) for b, l, w, p in nd["eqs"]]
    leg = nd["legacy"]
    if leg and leg["formal"]:
        rows.append(("Legacy record: Formal Expression", "Formal Expression", leg["formal"], "", ""))
    if not rows:
        rows.append(("NONE FOUND", "", "", "", ""))
    for src, block, latex, word, plain in rows:
        n += 1 if latex else 0
        ws.append([n if latex else "", nd["pos"], nd["id"], nd["label"], nd["mode"], nd["status"],
                   src, block, latex, word, plain, "", ""])

ws2 = wb.create_sheet("Nodes")
ws2.append(["Pos", "Node ID", "Node name", "Mode", "Status", "Tier", "# production eqs",
            "Has legacy formal?", "ID matches legacy?", "Statement", "Legacy formal expression",
            "Variables (Where:)", "Legacy limitations", "Kill condition", "Production file", "Legacy file"])
for nd in nodes:
    leg = nd["legacy"] or {}
    ws2.append([nd["pos"], nd["id"], nd["label"], nd["mode"], nd["status"], nd["tier"],
                len(nd["eqs"]), "yes" if leg.get("formal") else "NO",
                ("yes" if leg.get("id") == nd["id"] else f"NO ({leg.get('id', '')})") if leg else "no legacy file",
                nd["statement"], leg.get("formal", ""), nd["where"], leg.get("limitations", ""),
                nd["kill"], nd["file"], leg.get("file", "")])

head_fill = PatternFill("solid", fgColor="1F3864")
for sheet, widths in ((ws, [6, 5, 12, 32, 13, 12, 22, 26, 60, 40, 40, 14, 30]),
                      (ws2, [5, 12, 32, 13, 12, 22, 8, 8, 12, 50, 50, 40, 40, 40, 30, 30])):
    for c, w in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(c)].width = w
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
for row in ws.iter_rows(min_row=2):
    if row[6].value == "NONE FOUND":
        for cell in row:
            cell.fill = PatternFill("solid", fgColor="F8CBAD")
    elif row[6].value.startswith("Legacy"):
        row[6].fill = PatternFill("solid", fgColor="FFF2CC")

xlsx = OUT / "AXIOM_191_All_Equations.xlsx"
wb.save(xlsx)

# ---------------- Markdown paper ----------------
total_prod = sum(len(nd["eqs"]) for nd in nodes)
with_leg = sum(1 for nd in nodes if nd["legacy"] and nd["legacy"]["formal"])
no_prod = [nd for nd in nodes if not nd["eqs"]]
md = [
    "---", 'title: "AXIOM 191 — Complete Mathematical Compendium"', 'status: "review draft — equations unverified"',
    "---", "", "# AXIOM 191 — Complete Mathematical Compendium", "",
    "> [!warning] Review draft",
    "> Every equation below is copied verbatim from the 191 production nodes and their legacy sequential records.",
    "> Nothing has been corrected or checked. Use this to audit the math — mark verdicts in the Excel workbook.",
    "",
    f"- Nodes: **{len(nodes)}**",
    f"- Equations from production nodes (`$$` blocks): **{total_prod}**",
    f"- Nodes with a legacy *Formal Expression*: **{with_leg}**",
    f"- Nodes with **no** production math (legacy only): **{len(no_prod)}**",
    "",
    "Each node shows: the statement, the production math (rendered LaTeX), then the legacy Formal Expression",
    "(plain-text notation, as originally written). Where the two disagree, that is a review item.", "", "---", "",
]
for nd in nodes:
    leg = nd["legacy"] or {}
    md += [f"## {nd['pos']:03d} · {nd['id']} — {nd['label']}", "",
           f"`{nd['mode']}` · `{nd['status']}` · {nd['tier']}", ""]
    if nd["statement"]:
        md += [f"**Statement.** {nd['statement']}", ""]
    if nd["eqs"]:
        last = None
        for block, latex, word, plain in nd["eqs"]:
            if block != last:
                md += [f"**{block}**", ""]
                last = block
            md += ["$$", latex, "$$", ""]
            if word:
                md += [f"*Word equation:* {word}", ""]
        if nd["where"]:
            md += ["**Where:**", ""] + [f"- {l}" for l in nd["where"].splitlines()] + [""]
    else:
        md += ["*No `$$` math in the production node.*", ""]
    if leg.get("formal"):
        md += ["**Legacy Formal Expression**", "", "```", leg["formal"], "```", ""]
    if leg.get("limitations"):
        md += [f"*Limitations (legacy):* {leg['limitations']}", ""]
    if nd["kill"]:
        md += [f"*Kill condition:* {nd['kill']}", ""]
    md += ["---", ""]
paper = OUT / "AXIOM_191_All_Equations.md"
paper.write_text("\n".join(md), encoding="utf-8")

print(f"nodes={len(nodes)} production_eqs={total_prod} legacy_formal={with_leg} "
      f"no_production_math={len(no_prod)} excel_eq_rows={n}")
mism = [(nd['pos'], nd['id'], (nd['legacy'] or {}).get('id')) for nd in nodes
        if not nd['legacy'] or nd['legacy']['id'] != nd['id']]
print("legacy id mismatches:", mism)
print(xlsx)
print(paper)
