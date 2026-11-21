#!/usr/bin/env python3
"""
registry_scan.py - builds the canonical registry page for a folder of papers.

    python registry_scan.py "C:\\path\\to\\folder"            (page goes to .\\out\\)
    python registry_scan.py "C:\\path\\to\\folder" --out "C:\\path\\to\\folder\\_REGISTRY.html"

Read-only on the scanned folder. It writes exactly one file: the page.
One record per paper id. A step is marked done only when a receipt was found on disk.
Standard library only. Written by Claude with David, 2026-11-11.
"""
import argparse, datetime, hashlib, json, os, re, sys
from pathlib import Path

STEPS = [
    ("identity", "Identity", "ID"), ("draft", "Draft", "Draft"), ("audit", "Audit", "Audit"),
    ("deep", "Deep evaluation", "Deep"), ("ckg", "Knowledge graph", "Graph"), ("lean", "Lean proof", "Lean"),
    ("review", "Your review", "Review"), ("canon", "Canon", "Canon"), ("tts", "Read aloud", "Voice"),
    ("podcast", "Podcast", "Pod"), ("video", "Video", "Video"), ("published", "Published", "Live"),
]
AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
VIDEO = {".mp4", ".mov", ".webm", ".mkv"}
SKIP_DIRS = {".git", ".obsidian", "node_modules", "__pycache__", ".trash"}
DRAFT_MIN_WORDS = 600
MAX_DIRECT = 150          # files listed per folder in the browser
ID_RX = re.compile(r"^[A-Z][A-Z0-9]{1,7}\.\d{1,3}\.[A-Z0-9][A-Z0-9\-]*$")


def unq(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def parse_frontmatter(text):
    """Small YAML subset: scalars, inline lists, dash lists, dash lists of key/value blocks."""
    m = re.match(r"^\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", text, re.S)
    if not m:
        return {}, text, ""
    raw, body = m.group(1), text[m.end():]
    data, key, item = {}, None, None
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and re.match(r"^[A-Za-z_][\w \-]*:", s):
            k, _, v = s.partition(":")
            key, v, item = k.strip(), v.strip(), None
            if v == "":
                data[key] = None
            elif v.startswith("[") and v.endswith("]"):
                data[key] = [unq(x) for x in v[1:-1].split(",") if x.strip()]
            else:
                data[key] = unq(v)
        elif s.startswith("- ") and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            val = s[2:].strip()
            mm = re.match(r"^([A-Za-z_][\w\-]*):\s+(.*)$", val)
            if mm and val[0] not in "\"'":
                item = {mm.group(1): unq(mm.group(2))}
                data[key].append(item)
            else:
                item = None
                data[key].append(unq(val))
        elif indent > 0 and item is not None and ":" in s:
            k, _, v = s.partition(":")
            item[k.strip()] = unq(v)
    return data, body, raw


def read_text(p, limit=None):
    try:
        b = p.read_bytes() if limit is None else p.open("rb").read(limit)
    except OSError:
        return ""
    return b.decode("utf-8-sig", errors="replace")


def sha256(p):
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def iso(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def walk(root):
    """One pass over the tree: every directory with its file names."""
    dirs = {}
    for cur, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIP_DIRS)
        dirs[Path(cur)] = sorted(files)
    return dirs


def id_tokens(pid):
    """MIM.06.ACTS -> the spellings that show up in file names."""
    parts = pid.split(".")
    out = {pid.lower()}
    if len(parts) >= 2:
        out |= {f"{parts[0]}.{parts[1]}".lower(), f"{parts[0]}_{parts[1]}".lower()}
    if len(parts) >= 3:
        out.add("_".join(parts).lower())
    return out


def find_papers(root, dirs):
    """Markdown files, at the root or one folder down, whose frontmatter carries an id."""
    found = {}
    for d, files in dirs.items():
        rel = d.relative_to(root)
        if len(rel.parts) > 1:
            continue
        for name in files:
            if not name.lower().endswith(".md"):
                continue
            p = d / name
            fm, body, raw = parse_frontmatter(read_text(p))
            pid = str(fm.get("id") or "").strip()
            if not pid or not ID_RX.match(pid) or not (fm.get("uuid") or fm.get("type") == "paper"):
                continue
            found.setdefault(pid, []).append({"path": p, "fm": fm, "body": body, "raw": raw})
    # A file named exactly <id>.md with no frontmatter is still a copy of that paper.
    for d, files in dirs.items():
        if len(d.relative_to(root).parts) > 1:
            continue
        for name in files:
            pid = name[:-3]
            if name.lower().endswith(".md") and pid in found and all(c["path"] != d / name for c in found[pid]):
                fm, body, raw = parse_frontmatter(read_text(d / name))
                found[pid].append({"path": d / name, "fm": fm, "body": body, "raw": raw, "unregistered": True})
    return found


def norm_text(body):
    return re.sub(r"\s+", " ", body).strip()


def choose_primary(pid, copies, root):
    """The copy inside the paper's own folder is the record; others are listed as copies."""
    toks = id_tokens(pid)
    def score(c):
        rel = c["path"].relative_to(root)
        own = len(rel.parts) > 1 and any(t in rel.parts[0].lower() for t in toks)
        return (1 if c.get("unregistered") else 0, 0 if own else 1, -len(c["body"]), str(rel))
    return sorted(copies, key=score)


def evidence_for(pid, home, root, dirs):
    """Files that can count as receipts for this paper."""
    toks = id_tokens(pid)
    out = []
    home_is_root = home == root
    for d, files in dirs.items():
        try:
            rel = d.relative_to(home)
        except ValueError:
            continue
        if home_is_root and len(rel.parts) > 0 and rel.parts[0] != "API_RUNS":
            continue
        near = len(rel.parts) == 0 or (len(rel.parts) <= 2 and rel.parts[0] in (".data", "RESEARCH_DOSSIER", "API_CALLS", "audio", "media"))
        near = near and not (len(rel.parts) == 2 and rel.parts[0] == "RESEARCH_DOSSIER")
        for name in files:
            low = name.lower()
            if near or any(t in low for t in toks):
                out.append(d / name)
    api = root / "API_RUNS"
    if not home_is_root and api in dirs:
        out += [api / n for n in dirs[api] if any(t in n.lower() for t in toks)]
    return out


def load_receipts(pid, files):
    recs = []
    for p in files:
        if p.suffix.lower() != ".json":
            continue
        try:
            if p.stat().st_size > 300_000:
                continue
            j = json.loads(read_text(p))
        except (OSError, ValueError):
            continue
        if not isinstance(j, dict):
            continue
        if pid not in (j.get("parent_id"), j.get("parent_paper_id")):
            continue
        j["_file"] = p.name
        recs.append(j)
    return recs


def audit_applies(name, pid, position):
    up = name.upper()
    if "AUDIT" not in up:
        return False
    rng = re.search(r"PAPERS?_(\d+)_TO_(\d+)", up)
    if rng:
        return position is not None and int(rng.group(1)) <= position <= int(rng.group(2))
    other = re.findall(r"(?<![A-Z0-9])([A-Z]{2,6})[._](\d{1,3})(?![0-9])", up.replace("-", "_"))
    series, _, pos = pid.partition(".")
    pos = pos.split(".")[0]
    mine = [1 for s, n in other if s == series.upper() and n.lstrip("0") == pos.lstrip("0")]
    theirs = [1 for s, n in other if s == series.upper() and n.lstrip("0") != pos.lstrip("0")]
    return bool(mine) or not theirs


def step(state, receipts=None, note=""):
    return {"state": state, "receipts": receipts or [], "note": note}


def build_steps(pid, fm, body, files, receipts, all_names, audits_everywhere, position):
    names = [p.name for p in files]
    status = str(fm.get("status") or "").strip().lower()
    by_station = {}
    for r in receipts:
        by_station.setdefault(str(r.get("station_code") or r.get("station") or "").upper(), []).append(r)
    for run in as_list(fm.get("api_runs")):
        if isinstance(run, dict) and run.get("station"):
            by_station.setdefault(str(run["station"]).upper(), [])
    out = {}

    out["identity"] = step("done", [f"id {pid}", f"uuid {fm.get('uuid')}"]) if fm.get("uuid") else \
        step("missing", note="No UUID in the frontmatter.")

    words = len(re.findall(r"\w+", re.sub(r"^\s*>.*$", "", body, flags=re.M)))
    out["draft"] = step("done", [f"{words:,} words in the paper file"]) if words >= DRAFT_MIN_WORDS else \
        step("missing", note=f"{words:,} words. Under {DRAFT_MIN_WORDS} counts as an outline or stub.")

    aud = sorted({n for n in names if audit_applies(n, pid, position)} |
                 {n for n in audits_everywhere if re.search(r"PAPERS?_\d+_TO_\d+", n.upper()) and audit_applies(n, pid, position)})
    out["audit"] = step("done", aud[:6]) if aud else step("missing", note="No audit file found for this paper.")

    def station(codes, label):
        runs = [r for c in codes for r in by_station.get(c, [])]
        declared = any(c in by_station for c in codes)
        named = sorted(n for n in names if re.search(r"[._](%s)[._]" % "|".join(codes), n.upper()) and n.lower().endswith((".json", ".md")))
        if runs:
            return step("done", [f"{r.get('run_id') or r['_file']}  ({r['_file']})" for r in runs[:4]])
        if named:
            return step("done", named[:4])
        if declared:
            return step("claimed", note=f"Frontmatter lists a {label} run, but its receipt file was not found here.")
        return step("missing", note=f"No {label} receipt found.")

    out["deep"] = station(["DEEP", "DS"], "deep evaluation")
    for r in by_station.get("DEEP", []) + by_station.get("DS", []):
        f = r.get("response_markdown_file")
        if f and f.lower() not in all_names:
            out["deep"] = step("claimed", out["deep"]["receipts"], f"Receipt names {f}, which was not found under this folder.")
    out["ckg"] = station(["CKG"], "knowledge graph")

    lean_na = str(fm.get("lean") or "").strip().lower() in ("n/a", "na", "none", "not_applicable")
    lean_files = sorted(n for n in names if n.lower().endswith(".lean"))
    lr = by_station.get("LEAN", [])
    if lean_na:
        out["lean"] = step("na", note="Marked as not applicable in the frontmatter.")
    elif lean_files:
        out["lean"] = step("done", lean_files[:4])
    elif lr:
        r = lr[0]
        lf = r.get("lean_file")
        rec = [f"{r.get('run_id') or r['_file']}  ({r['_file']})"] + [f"theorem {t}" for t in as_list(r.get("theorems_proven"))[:5]]
        if lf and lf.lower() not in all_names:
            out["lean"] = step("claimed", rec, f"Receipt names {lf}, but that file is not under this folder, so the proof could not be checked here.")
        elif r.get("compiled") is False:
            out["lean"] = step("missing", rec, "Receipt says the Lean file did not compile.")
        else:
            out["lean"] = step("done", rec)
    else:
        out["lean"] = station(["LEAN"], "Lean")

    reviewed = status in ("reviewed", "review_passed", "candidate", "canon", "canonical", "published") or \
        str(fm.get("review") or "").lower() in ("true", "yes", "done", "passed", "accepted")
    out["review"] = step("done", [f"status: {status or fm.get('review')}"]) if reviewed else \
        step("missing", note=f"Status is \"{status or 'not set'}\". No review ruling recorded.")
    canon = status in ("canon", "canonical") or str(fm.get("canon") or "").lower() in ("canon", "canonical", "true")
    out["canon"] = step("done", [f"status: {status}"]) if canon else step("missing", note="Not admitted to canon.")

    audio = [n for n in names if Path(n).suffix.lower() in AUDIO]
    pod = sorted(n for n in audio if re.search(r"(^|[._\-])(POD|PODCAST)([._\-]|$)", n.upper()))
    tts = sorted(n for n in audio if n not in pod)
    vid = sorted(n for n in names if Path(n).suffix.lower() in VIDEO)
    out["tts"] = step("done", tts[:4]) if tts else step("missing", note="No narration audio found.")
    out["podcast"] = step("done", pod[:4]) if pod else step("missing", note="No podcast audio found.")
    out["video"] = step("done", vid[:4]) if vid else step("missing", note="No video file found.")
    url = fm.get("published_url") or fm.get("url")
    pub = status == "published" or str(fm.get("published") or "").lower() in ("true", "yes") or bool(fm.get("published_url"))
    out["published"] = step("done", [str(url or "status: published")]) if pub else step("missing", note="Not published.")
    return out


def previous_data(out_path):
    if not out_path.exists():
        return None
    m = re.search(r'<script id="registry-data" type="application/json">(.*?)</script>', read_text(out_path), re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1).replace("<\\/", "</"))
    except ValueError:
        return None


def diff_history(prev, papers, now):
    hist = list((prev or {}).get("history", []))
    if prev is None:
        hist.append({"at": now, "what": f"First scan. {len(papers)} papers recorded."})
        return hist
    old = {p["id"]: p for p in prev.get("papers", [])}
    new = {p["id"]: p for p in papers}
    labels = {k: lab for k, lab, _ in STEPS}
    for pid in sorted(new.keys() - old.keys()):
        hist.append({"at": now, "paper": pid, "what": "Paper added to the registry."})
    for pid in sorted(old.keys() - new.keys()):
        hist.append({"at": now, "paper": pid, "what": "Paper no longer found in this folder."})
    for pid in sorted(new.keys() & old.keys()):
        a, b = old[pid], new[pid]
        if a.get("sha256") != b.get("sha256"):
            hist.append({"at": now, "paper": pid, "what": "Paper file changed."})
        if a.get("path") != b.get("path"):
            hist.append({"at": now, "paper": pid, "what": f"Moved from {a.get('path')} to {b.get('path')}."})
        for k, lab in labels.items():
            sa, sb = a.get("steps", {}).get(k, {}).get("state"), b["steps"][k]["state"]
            if sa and sa != sb:
                hist.append({"at": now, "paper": pid, "what": f"{lab}: {sa} to {sb}."})
    return hist[-600:]


def load_fis(fis_dir):
    """The existing FIS engine supplies the Master Equation name, keywords and addresses."""
    if not fis_dir or not Path(fis_dir, "fis_folder_memory.py").is_file():
        return None
    sys.path.insert(0, str(fis_dir))
    try:
        import fis_folder_memory as F
        return F
    except Exception as e:                      # the registry still builds without it
        print(f"FIS engine not loaded ({type(e).__name__}: {e}). Master Equation names will be blank.")
        return None


def fis_fields(F, p):
    if F is None:
        return None
    try:
        c = F.classify_file(str(p), folder_class="")
        kw = F.local_keywords(p, c)
        chi = c.get("chi") or {}
        st = p.stat()
        prop = F.propose_name({
            "name": p.name, "path": str(p), "ext": p.suffix.lower(), "mtime": st.st_mtime,
            "chi_domain": (c.get("domain") or {}).get("name", ""), "content_type": c.get("content_type", ""),
            "chi_confidence": c.get("confidence", 0.0), "sample": " ".join(kw),
        })
        law, dom = c.get("law") or {}, c.get("domain") or {}
        return {
            "me_name": F.meq_namer_string(chi), "me_short": F.meq_namer_short(chi), "chi": chi,
            "chi_factor": c.get("chi_factor"), "chi_name": c.get("chi_name"),
            "law": law.get("name"), "domain": dom.get("name"), "content_type": c.get("content_type"),
            "role": c.get("file_role"), "doc_type": c.get("doc_type"), "confidence": c.get("confidence"),
            "evidence": (c.get("structural_evidence") or {}).get("total_score"),
            "proof_gaps": (c.get("structural_evidence") or {}).get("proof_gaps") or [],
            "keywords": kw, "lossless": F.file_lossless_address(p).get("address"),
            "proposed_name": prop.get("proposed_name"),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def scan(root, out_path, F=None):
    root = root.resolve()
    dirs = walk(root)
    all_names = {n.lower() for files in dirs.values() for n in files}
    found = find_papers(root, dirs)
    audits_everywhere = sorted({n for files in dirs.values() for n in files if "AUDIT" in n.upper()})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    papers, title_index = [], {}

    for pid, copies in found.items():
        ordered = choose_primary(pid, copies, root)
        main = ordered[0]
        fm, body, p = main["fm"], main["body"], main["path"]
        home = p.parent
        try:
            position = int(str(fm.get("position") or pid.split(".")[1]))
        except (ValueError, IndexError):
            position = None
        files = evidence_for(pid, home, root, dirs)
        receipts = load_receipts(pid, files)
        steps = build_steps(pid, fm, body, files, receipts, all_names, audits_everywhere, position)
        main_hash = sha256(p)
        links = sorted({m.strip() for m in re.findall(r"\[\[([^\]|#]+)", body)})
        edges = [{"to": e.get("to"), "relation": e.get("relation") or "linked"}
                 for r in receipts for e in as_list(r.get("cross_paper_edges")) if isinstance(e, dict) and e.get("to")]
        st = p.stat()
        rec = {
            "id": pid, "title": fm.get("title") or p.stem, "series": fm.get("series") or pid.split(".")[0],
            "position": position, "uuid": fm.get("uuid"), "short_uuid": fm.get("short_uuid"),
            "type": fm.get("type"), "status": fm.get("status"),
            "me_name": fm.get("me_name") or fm.get("master_equation_name") or fm.get("me_namer"),
            "aliases": [a for a in as_list(fm.get("aliases")) if isinstance(a, str)],
            "tags": [t for t in as_list(fm.get("tags")) if isinstance(t, str)],
            "keywords": [t for t in as_list(fm.get("keywords")) if isinstance(t, str)],
            "laws": as_list(fm.get("laws")), "card": fm.get("card"),
            "path": p.relative_to(root).as_posix(), "folder": home.relative_to(root).as_posix() if home != root else "",
            "size": st.st_size, "modified": iso(st.st_mtime), "sha256": main_hash,
            "copies": [{"path": c["path"].relative_to(root).as_posix(),
                        "same": norm_text(c["body"]) == norm_text(body),
                        "registered": not c.get("unregistered")} for c in ordered[1:]],
            "shown_in": [], "links_out_raw": links, "edges": edges, "steps": steps,
            "frontmatter": main["raw"], "evidence_files": len(files), "fis": fis_fields(F, p),
        }
        if not rec["me_name"] and rec["fis"] and rec["fis"].get("me_name"):
            rec["me_name"] = rec["fis"]["me_name"]
        papers.append(rec)
        for key in [pid, rec["title"]] + rec["aliases"]:
            title_index[str(key).lower()] = pid

    by_id = {p["id"]: p for p in papers}
    for p in papers:
        out = {}
        for e in p.pop("edges"):
            if e["to"] in by_id and e["to"] != p["id"]:
                out[e["to"]] = e["relation"]
        for l in p.pop("links_out_raw"):
            t = title_index.get(l.lower())
            if t and t != p["id"]:
                out.setdefault(t, "links to")
        p["relates_out"] = [{"id": k, "relation": v} for k, v in sorted(out.items())]
    for p in papers:
        p["relates_in"] = [{"id": q["id"], "relation": r["relation"]} for q in papers for r in q["relates_out"] if r["id"] == p["id"]]
    papers.sort(key=lambda p: (str(p["series"]), p["position"] if p["position"] is not None else 999, p["id"]))

    totals = {}
    for d, files in dirs.items():
        for anc in [d] + list(d.parents):
            totals[anc] = totals.get(anc, 0) + len(files)
            if anc == root:
                break

    def listing(d):
        files = dirs.get(d, [])
        rows = []
        for n in files[:MAX_DIRECT]:
            try:
                s = (d / n).stat()
                rows.append({"name": n, "size": s.st_size, "modified": iso(s.st_mtime)})
            except OSError:
                rows.append({"name": n, "size": None, "modified": None})
        subs = [{"name": c.name, "files": totals.get(c, 0)} for c in sorted(x for x in dirs if x.parent == d)]
        return {"files": rows, "more_files": max(0, len(files) - MAX_DIRECT), "subfolders": subs}

    folders = [{"name": "", "label": root.name, "total": totals.get(root, 0), **listing(root)}]
    for c in sorted(x for x in dirs if x.parent == root):
        folders.append({"name": c.name, "label": c.name, "total": totals.get(c, 0), **listing(c)})

    prev = previous_data(out_path)
    data = {
        "schema": "theophysics.registry/1.0", "root": str(root), "root_name": root.name, "scanned_at": now,
        "steps": [{"key": k, "label": lab, "short": sh} for k, lab, sh in STEPS],
        "papers": papers, "folders": folders, "total_files": totals.get(root, 0),
        "history": diff_history(prev, papers, now),
    }
    return data


def write_page(data, out_path):
    template = (Path(__file__).parent / "registry_template.html").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = template.replace("__REGISTRY_JSON__", blob).replace("__PAGE_TITLE__", f"Registry · {data['root_name']}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".saving")
    tmp.write_text(page, encoding="utf-8", newline="\n")
    tmp.replace(out_path)


def main():
    ap = argparse.ArgumentParser(description="Build the registry page for a folder of papers.")
    ap.add_argument("folder")
    ap.add_argument("--out", help="Where to write the page. Default: .\\out\\<folder name>_REGISTRY.html")
    ap.add_argument("--fis", default=r"D:\GitHub\David-OSv3\file-intelligence-system",
                    help="Folder holding the FIS engine (fis_folder_memory.py). Supplies Master Equation names and keywords.")
    a = ap.parse_args()
    root = Path(a.folder)
    if not root.is_dir():
        sys.exit(f"Not a folder: {root}")
    safe = re.sub(r"[^\w\-]+", "_", root.resolve().name).strip("_")
    out = Path(a.out) if a.out else Path(__file__).parent / "out" / f"{safe}_REGISTRY.html"
    data = scan(root, out, load_fis(a.fis))
    write_page(data, out)
    done = sum(1 for p in data["papers"] for s in p["steps"].values() if s["state"] == "done")
    print(f"{len(data['papers'])} papers, {data['total_files']:,} files seen, {done} steps with receipts.")
    print(f"Page: {out}")


if __name__ == "__main__":
    main()
