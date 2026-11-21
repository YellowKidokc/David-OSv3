"""Renamer engine — proposes hybrid names from context clue words, applies them safely, undoes them.

    DOMAIN__TYPE__words_in_lowercase__YYYYMMDD__ST.ext     (rules: rename_rules.yaml)

Nothing renames without a checked row and an explicit Apply. Every apply writes a ledger
(before/after path, sha256, confidence, decision) that `undo_run` can roll back, and rewrites
Obsidian [[links]] inside the scanned folder so renamed notes stay linked. Spreadsheet rules
honoured: GR-003/004 protect, GR-005 ledger, GR-006 preview, GR-008 hash, GR-011 rollback,
DER-001 exact duplicates are flagged, never deleted.

    python rename_engine.py "S:\\PROCESSED"            print proposals (dry run)
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RULES = HERE / "rename_rules.yaml"
LEDGER = HERE / "data" / "rename_ledger.csv"  # used by apply() only
LEDGER_COLS = ["run", "when", "root", "old_path", "new_path", "sha256", "confidence",
               "proposed", "final", "decision", "links_updated"]
NAMED = re.compile(r"^[A-Z]{3}__[A-Z]{3}__[a-z0-9_]+__\d{8}__[A-Z]{2}$")   # already in the scheme
ROMAN = re.compile(r"^[ivx]+[a-z]?$")

_REPO = HERE.parents[1]                      # David-OSv3
for _p in (_REPO, _REPO / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
# [David-OS apps/rename] The gate/ledger/profile modules are only used by apply()/undo,
# which this app never calls (proposal-only). Optional here so propose() runs standalone.
try:
    import gate as _gate                          # noqa: E402
    import ledger as _ledger                      # noqa: E402
    from hub.config.folder_profiles import FolderProfileRegistry as _Profiles  # noqa: E402
except ImportError:
    _gate = _ledger = _Profiles = None

GATE_ERRORS: list[str] = []                   # details of the last blocked batch


def _gate_decision(action_id: str, paths: list[Path], root: Path):
    profile_err = None
    try:
        reg = _Profiles.load(_REPO / "config" / "folder_profiles.json")
        prof = reg.match(root)
        profile = prof.to_payload()
        if prof is reg.default:
            # no real profile claimed this folder — drop the default floor so the
            # rulebook's per-action approval_default becomes the floor instead
            profile.pop("approval_floor", None)
    except Exception as e:                    # fail closed, loudly
        profile = {}
        profile_err = f"profile load error: {e}"
        GATE_ERRORS[:] = [profile_err]
    g = _gate.Gate.load(_REPO / "config" / "rules", profile)
    if profile_err and not g.load_error:      # a corrupt registry must degrade to ASK-everything
        g.load_error = profile_err
    return g.evaluate(action_id, [str(p) for p in paths],
                      {"batch_size": len(paths)})


@dataclass
class Proposal:
    path: Path
    proposed: str
    confidence: float
    why: list[str] = field(default_factory=list)
    domain: str = ""
    type: str = ""
    status: str = ""
    sha256: str = ""
    flag: str = ""            # duplicate / collision / already named / protected: shown, not checked
    links_in: int = 0         # other notes in the folder that [[link]] to this one


def load_rules() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))


def _rx(word: str) -> re.Pattern:
    w = re.escape(word.lower()).replace(r"\ ", r"[\s_\-]+")
    return re.compile(rf"\b{w}\b" if len(word) <= 4 else rf"\b{w}")


def _match(table: list[dict], name: str, title: str, body: str,
           folder: str = "") -> tuple[str, str, float] | None:
    """Name beats title beats folder beats body. In name/title/folder the first rule wins (rule
    order = priority); in the body the rule mentioned most often wins, with at least 3 mentions."""
    for where, text, weight in (("name", name, 0.35), ("title", title, 0.25), ("folder", folder, 0.20)):
        for rule in table:
            for w in rule["words"]:
                if _rx(w).search(text):
                    return rule["code"], f"{rule['code']} ← '{w}' in {where}", weight
    if body:
        counts = {r["code"]: sum(len(_rx(w).findall(body)) for w in r["words"]) for r in table}
        code, n = max(counts.items(), key=lambda kv: kv[1])
        if n >= 3:
            return code, f"{code} ← mentioned {n}× in text", 0.12
    return None


def _clean(text: str) -> str:
    text = re.sub(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
    text = text.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _words(stem: str, title: str, rules: dict) -> tuple[str, list[str]]:
    why, s = [], _clean(stem)
    lead = ""
    for sr in rules["series"]:
        m = re.match(sr["pattern"], stem.lower().replace(" - ", "_"))
        if m:
            n = m.group(1)
            x = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            lead = sr["as"].replace("{n}", f"{int(n):02d}").replace("{x}", x or "")
            s = _clean(stem.lower().replace(" - ", "_")[m.end():])
            why.append(f"order kept: {lead}")
            break
    drop = set(rules["drop_words"])
    words = [w for w in s.split() if w not in drop and len(w) > 1 and not ROMAN.match(w)]
    if len(words) < 2 and title:
        words = [w for w in _clean(title).split() if w not in drop and len(w) > 1][:rules["max_words"]]
        why.append("words from title")
    words = words[:rules["max_words"]]
    out = "_".join(([lead] if lead else []) + words) or "untitled"
    return out, why


def _read(path: Path) -> tuple[str, str, bytes]:
    data = path.read_bytes()
    text = data[:20000].decode("utf-8", errors="replace")
    title = ""
    for line in text.splitlines():
        if line.startswith("title:"):
            title = line[6:].strip().strip("'\""); break
        if line.startswith("# "):
            title = line[2:].strip(); break
    return title, text[:4000], data


def propose(root: Path, recursive: bool = True, rules: dict | None = None) -> list[Proposal]:
    rules = rules or load_rules()
    files = sorted(p for p in (root.rglob("*") if recursive else root.glob("*")) if p.is_file())
    out: list[Proposal] = []
    for p in files:
        if any(part in rules["protect"] for part in p.parts) or p.name.startswith("."):
            continue
        try:
            title, body, data = _read(p)
        except OSError as e:
            out.append(Proposal(p, p.name, 0.0, [f"unreadable: {e}"], flag="unreadable")); continue
        name_l, title_l, body_l = _clean(p.stem), _clean(title), _clean(body)
        why: list[str] = []
        conf = 0.30
        folder_l = _clean(" ".join(p.parent.relative_to(root).parts))
        d = _match(rules["domains"], name_l, title_l, body_l, folder_l)
        domain = d[0] if d else rules["domain_fallback"]
        why.append(d[1] if d else f"{domain} ← no domain clue (guess)")
        conf += d[2] if d else -0.15
        t = _match(rules["types"], name_l, title_l, "")
        typ = t[0] if t else rules["type_fallback"]
        why.append(t[1] if t else f"{typ} ← default type")
        conf += t[2] if t else 0.0
        st = _match(rules["status"], name_l, title_l, "")
        mtime = p.stat().st_mtime
        status = st[0] if st else (
            "AR" if (time.time() - mtime) / 86400 > rules["archive_after_days"] else rules["status_fallback"])
        if st:
            why.append(st[1])
        words, wwhy = _words(p.stem, title, rules)
        why += wwhy
        conf += 0.10 if len(words.split("_")) >= 3 else -0.10
        date = dt.datetime.fromtimestamp(mtime).strftime("%Y%m%d")
        name = f"{domain}__{typ}__{words}__{date}__{status}"
        ext = p.suffix.lower()
        if len(name) + len(ext) > rules["max_length"]:
            name = name[: rules["max_length"] - len(ext)].rstrip("_")
        pr = Proposal(p, name + ext, round(max(0.05, min(conf, 0.97)), 2), why, domain, typ, status,
                      hashlib.sha256(data).hexdigest())
        if NAMED.match(p.stem):
            pr.flag, pr.proposed, pr.confidence = "already named", p.name, 1.0
        out.append(pr)
    _count_links(root, out)
    _flag_duplicates_and_collisions(out)
    return out


def _flag_duplicates_and_collisions(props: list[Proposal]) -> None:
    by_hash: dict[str, Proposal] = {}
    for pr in props:
        if pr.flag:
            continue
        first = by_hash.setdefault(pr.sha256, pr)
        if first is not pr:
            pr.flag = f"duplicate of {first.path.name}"
            pr.why.append("identical bytes (sha256) — flagged, not deleted")
    # Same target name: the copy other notes link to most (then the newest) keeps it.
    groups: dict[Path, list[Proposal]] = {}
    for pr in props:
        if not pr.flag:
            groups.setdefault(pr.path.with_name(pr.proposed), []).append(pr)
    for target, group in groups.items():
        if target.exists() and target not in [p.path for p in group]:
            for pr in group:
                pr.flag = "name collision"
                pr.why.append("a file with this name already exists")
            continue
        group.sort(key=lambda p: (p.links_in, p.path.stat().st_mtime), reverse=True)
        for pr in group[1:]:
            pr.flag = "name collision"
            pr.why.append(f"'{group[0].path.name}' keeps this name (more links / newer)")


def _count_links(root: Path, props: list[Proposal]) -> None:
    notes = [p for p in root.rglob("*.md") if not any(x in p.parts for x in (".obsidian", "ZZZ_DELETE"))]
    texts = []
    for n in notes:
        try:
            texts.append(n.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    blob = "\n".join(texts)
    for pr in props:
        if pr.path.suffix.lower() == ".md":
            pr.links_in = len(re.findall(r"\[\[" + re.escape(pr.path.stem) + r"(?:[#|\]])", blob))
            if pr.links_in:
                pr.why.append(f"linked from {pr.links_in} place(s) — links get updated")


def _rewrite_links(root: Path, stems: dict[str, str], backup: Path) -> dict[str, int]:
    """One pass over the folder, after all renames: [[old]] -> [[new]] for every renamed note.
    Each edited note is backed up first and keeps its original modified date."""
    if not stems:
        return {}
    pat = re.compile(r"\[\[(" + "|".join(re.escape(s) for s in sorted(stems, key=len, reverse=True)) + r")(?=[#|\]])")
    per_stem: dict[str, int] = {}

    def sub(m: re.Match) -> str:
        per_stem[m.group(1)] = per_stem.get(m.group(1), 0) + 1
        return "[[" + stems[m.group(1)]

    for n in root.rglob("*.md"):
        if any(x in n.parts for x in (".obsidian", "ZZZ_DELETE")):
            continue
        try:
            text = n.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new = pat.sub(sub, text)
        if new != text:
            st = n.stat()
            dst = backup / n.relative_to(root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(n, dst)
            n.write_text(new, encoding="utf-8")
            os.utime(n, ns=(st.st_atime_ns, st.st_mtime_ns))
    return per_stem


def apply(root: Path, rows: list[tuple[Proposal, str, str]], override: bool = False) -> tuple[str, int, list[str]]:
    """rows: (proposal, final_name, decision). decision 'rename' renames; others are only logged.
    override must be True when the gate answered ASK and a human approved (the GUI dialog does this).
    Returns (run_id, renamed_count, errors)."""
    GATE_ERRORS.clear()
    mutating = [pr for pr, _final, dec in rows if dec == "rename"]
    gdec = _gate_decision("rename", [pr.path for pr in mutating], root)
    if gdec.verdict in (_gate.BLOCK, _gate.DROP):
        GATE_ERRORS[:] = [f"{r['rule_id']}: {r['reason']}" for r in gdec.fired_rules]
        _ledger.log_event("gate_decision", path=str(root), folder=str(root), action_id="rename",
                          verdict=gdec.verdict, fired=gdec.fired_rules)
        return "", 0, list(GATE_ERRORS)
    if gdec.verdict == _gate.ASK and not override:
        GATE_ERRORS[:] = ["approval required: " + "; ".join(
            f"{r['rule_id']}: {r['reason']}" for r in gdec.fired_rules)]
        _ledger.log_event("gate_decision", path=str(root), folder=str(root), action_id="rename",
                          verdict="ask", choice="no_override", fired=gdec.fired_rules)
        return "", 0, list(GATE_ERRORS)
    if gdec.verdict == _gate.ASK:
        _ledger.log_event("gate_decision", path=str(root), folder=str(root), action_id="rename",
                          verdict="ask", fired=gdec.fired_rules)
        # caller passed override=True — a human approved this batch.
    run = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = HERE / "data" / "link_backups" / run
    LEDGER.parent.mkdir(exist_ok=True)
    errors: list[str] = []
    results = []                       # (proposal, final, decision, new_path)
    for pr, final, decision in rows:   # 1) every rename, each checked against its scan-time hash
        new_path = pr.path
        if decision == "rename" and final and final != pr.path.name:
            target = pr.path.with_name(final)
            try:
                if target.exists():
                    raise FileExistsError(f"{final} already exists")
                if hashlib.sha256(pr.path.read_bytes()).hexdigest() != pr.sha256:
                    raise RuntimeError("file changed since scan — rescan first")
                pr.path.rename(target)
                new_path = target
            except Exception as e:  # noqa: BLE001
                errors.append(f"{pr.path.name}: {e}")
                decision = f"error: {e}"
        results.append((pr, final, decision, new_path))
    stems = {pr.path.stem: np.stem for pr, _, _, np in results              # 2) then links, once
             if np != pr.path and pr.path.suffix.lower() == ".md" and pr.links_in}
    links = _rewrite_links(root, stems, backup)
    new_file = not LEDGER.exists()
    with open(LEDGER, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(LEDGER_COLS)
        for pr, final, decision, new_path in results:
            w.writerow([run, dt.datetime.now().isoformat(timespec="seconds"), str(root), str(pr.path),
                        str(new_path), pr.sha256, pr.confidence, pr.proposed, final, decision,
                        links.get(pr.path.stem, 0) if new_path != pr.path else 0])
    return run, sum(1 for r in results if r[3] != r[0].path), errors


def runs() -> list[str]:
    if not LEDGER.exists():
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return sorted({r["run"] for r in csv.DictReader(f) if r["old_path"] != r["new_path"]}, reverse=True)


def undo_run(run: str) -> tuple[int, list[str]]:
    """Rename every file of `run` back and restore the notes whose links were rewritten."""
    with open(LEDGER, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["run"] == run and r["old_path"] != r["new_path"]]
    undone, errors = 0, []
    backup = HERE / "data" / "link_backups" / run
    if backup.is_dir() and rows:       # 1) restore link-edited notes while they still have their new names
        root = Path(rows[0]["root"])
        for b in backup.rglob("*.md"):
            shutil.copy2(b, root / b.relative_to(backup))
    for r in reversed(rows):           # 2) then rename everything back
        new, old = Path(r["new_path"]), Path(r["old_path"])
        try:
            if old.exists():
                raise FileExistsError(f"{old.name} exists again")
            new.rename(old)
            undone += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{new.name}: {e}")
    with open(LEDGER, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([run, dt.datetime.now().isoformat(timespec="seconds"), "", "", "", "",
                                "", "", "", f"undone {undone}", ""])
    return undone, errors


def scoreboard() -> tuple[int, int]:
    """Engine measurement: of the rows you decided, how many did you take exactly as proposed?"""
    if not LEDGER.exists():
        return 0, 0
    right = total = 0
    with open(LEDGER, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["decision"] in ("rename", "reject"):
                total += 1
                right += r["decision"] == "rename" and r["final"] == r["proposed"]
    return right, total


def export_xlsx(props: list[Proposal], finals: dict[str, str], checked: set[str], dst: Path) -> Path:
    """The same review sheet as a spreadsheet: A check, B original, C proposed, D engine, E why, F override."""
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rename review"
    ws.append(["✓", "Original name", "Proposed name", "Engine confidence", "Why (clue words)",
               "Your override", "Flag", "Folder"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for pr in props:
        key = str(pr.path)
        ws.append(["✓" if key in checked else "", pr.path.name, pr.proposed, pr.confidence,
                   "; ".join(pr.why), finals.get(key, "") if finals.get(key) != pr.proposed else "",
                   pr.flag, str(pr.path.parent)])
    for col, width in zip("ABCDEFGH", (4, 48, 62, 10, 70, 30, 22, 40)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "B2"
    wb.save(dst)
    return dst


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = Path(sys.argv[1] if len(sys.argv) > 1 else r"S:\PROCESSED")
    for pr in propose(root):
        print(f"{pr.confidence:.2f}  {pr.flag or '':<16} {pr.path.name}\n      -> {pr.proposed}   [{'; '.join(pr.why)}]")
