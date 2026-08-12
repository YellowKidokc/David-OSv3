#!/usr/bin/env python3
"""FIS-Atlas CLI. Preview-only — never moves, renames, or deletes.

    python run_atlas.py <folder>              build atlas -> JSON in _atlas_out/
    python run_atlas.py <folder> --html       + render the gold-on-black page
    python run_atlas.py <folder> --fisnotes   + emit .fisnote v2 (to _atlas_out/)
    python run_atlas.py <folder> --in-place   write .fisnote INTO each folder (opt-in)
"""
from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

from fis.atlas import build_atlas, build_report
from fis import render, fisnote, report as report_mod


def main(argv):
    if not argv:
        print(__doc__); return 1
    root = argv[0]
    if not Path(root).is_dir():
        print(f"Not a folder: {root}"); return 1

    flags = set(argv[1:])
    out = Path("_atlas_out")
    out.mkdir(exist_ok=True)

    print(f"Scanning (preview-only): {root}")
    atlas = build_atlas(root)
    print(f"  {len(atlas.objects)} files · {len(atlas.folders)} folders · {len(atlas.clusters)} clusters")

    jpath = out / "atlas.json"
    jpath.write_text(json.dumps(atlas.to_dict(), indent=2, default=str), encoding="utf-8")
    print(f"  atlas JSON -> {jpath}")

    # SQLite store (the brain) — always written
    from fis.store import Store
    st = Store(out / "atlas.db")
    stats = st.save_atlas(atlas)
    st.close()
    print(f"  SQLite store -> {out / 'atlas.db'}  "
          f"({stats['objects_written']} written, {stats['objects_unchanged']} unchanged via mtime)")

    for c in atlas.clusters:
        print(f"    · {c.label}")

    if "--html" in flags:
        hpath = out / "atlas.html"
        hpath.write_text(render.render_html(atlas), encoding="utf-8")
        print(f"  atlas HTML -> {hpath}")
        try:
            webbrowser.open(hpath.resolve().as_uri())
        except Exception:
            pass

    if "--report" in flags or "--html" in flags:
        model = build_report(atlas)
        (out / "report_model.json").write_text(json.dumps(model, indent=2, default=str), encoding="utf-8")
        rpath = out / "report.html"
        rpath.write_text(report_mod.render_report(model, atlas.root), encoding="utf-8")
        print(f"  report_model.json + report -> {rpath}")
        print(f"    {len(model['findings'])} findings · {len(model['open_questions'])} open questions")
        for q in model["open_questions"][:3]:
            print(f"      ? [{q['priority']}] {q['question']}")
        if "--html" in flags:
            try:
                webbrowser.open(rpath.resolve().as_uri())
            except Exception:
                pass

    if "--fisnotes" in flags or "--in-place" in flags:
        written = fisnote.emit_all(atlas, out, in_place=("--in-place" in flags))
        where = "IN PLACE (.fisnote in each folder)" if "--in-place" in flags else str(out / "fisnotes")
        print(f"  emitted {len(written)} fisnote(s) -> {where}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
