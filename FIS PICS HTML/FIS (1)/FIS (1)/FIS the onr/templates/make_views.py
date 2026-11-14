"""Build Keyword Atlas + Brown Graphic views from FIS folder-brain HTML pages,
collect them in ONE output folder, and build an aggregate across all folders.

Usage:
  python make_views.py <source folder or fis.html> [more sources...] [--out OUTDIR]
Default OUTDIR: ./FIS_VIEWS
Output:
  OUTDIR/<folder>.keywords.html, OUTDIR/<folder>.graphic.html   (one pair per FIS page)
  OUTDIR/_ALL.keywords.html, OUTDIR/_ALL.graphic.html, OUTDIR/_ALL.json  (aggregate)
"""
import re, sys, json, pathlib

HERE = pathlib.Path(__file__).parent
TPL = {s: (HERE / f"{s}.tpl.html").read_text(encoding="utf8") for s in ("keywords", "graphic")}
REC = re.compile(r'<script type="application/json" id="fis-folder-record">(.*?)</script>', re.S)
SKIP = (".keywords.html", ".graphic.html", ".tpl.html")


def write_views(record: dict, outdir: pathlib.Path, stem: str):
    payload = json.dumps(record, ensure_ascii=False).replace("</", "<\\/")
    for suffix, tpl in TPL.items():
        (outdir / f"{stem}.{suffix}.html").write_text(tpl.replace("/*FIS_RECORD*/", payload), encoding="utf8")


def main(argv):
    out = pathlib.Path("FIS_VIEWS")
    if "--out" in argv:
        i = argv.index("--out"); out = pathlib.Path(argv[i + 1]); del argv[i:i + 2]
    out.mkdir(parents=True, exist_ok=True)
    sources = [pathlib.Path(a) for a in argv] or [pathlib.Path(".")]

    records, seen = [], set()
    for src in sources:
        for p in ([src] if src.is_file() else src.rglob("*.html")):
            if p.name.endswith(SKIP) or out.resolve() in p.resolve().parents:
                continue
            m = REC.search(p.read_text(encoding="utf8", errors="replace"))
            if not m:
                continue
            try:
                rec = json.loads(m.group(1))
            except json.JSONDecodeError:
                print("bad JSON, skipped:", p); continue
            fid = rec.get("folder", {}).get("folder_id") or str(p)
            if fid in seen:
                continue
            seen.add(fid)
            name = rec.get("folder", {}).get("name") or p.stem
            stem = re.sub(r'[\\/:*?"<>|]+', "_", name)
            if (out / f"{stem}.keywords.html").exists() and stem in {r[1] for r in records}:
                stem += "_" + fid[-6:]
            write_views(rec, out, stem)
            records.append((rec, stem))
            print("built", stem, "<-", p)

    # Aggregate: every file from every folder, tagged with its folder
    files, sig_sum = [], {}
    for rec, stem in records:
        fname = rec.get("folder", {}).get("name", stem)
        for f in rec.get("files", []):
            g = dict(f); g["name"] = f"{fname} / {f.get('name','')}"; g["folder"] = fname
            files.append(g)
        for k, v in (rec.get("signals") or {}).items():
            if isinstance(v, (int, float)):
                sig_sum.setdefault(k, []).append(v)
    agg = {
        "schema": "fis.aggregate/1",
        "folder": {"name": f"ALL FOLDERS ({len(records)})", "path": "; ".join(map(str, sources)),
                   "compressed_name": "AGGREGATE", "meq_aggregate": "",
                   "folders": [r[0].get("folder", {}).get("name") for r in records]},
        "files": files,
        "signals": {k: round(sum(v) / len(v)) for k, v in sig_sum.items()},
    }
    if records:
        write_views(agg, out, "_ALL")
        (out / "_ALL.json").write_text(json.dumps(agg, indent=1, ensure_ascii=False), encoding="utf8")
    print(f"{len(records)} folder(s), {len(files)} file(s) -> {out.resolve()}")


main(sys.argv[1:])
