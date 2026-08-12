#!/usr/bin/env python3
"""Visual matcher (W9) — find the same slide across PDF / PNG / WebP.

    python run_visual.py "<folder>" [--aperture=tight|normal|wide]

Real pipeline: render PDF pages, perceptual-hash every image + page, group the
cross-format families, and stage a preview into NOT_LOGGED/ with a CSV + a
manifest. Nothing moves. Needs Pillow (+ PyMuPDF for PDFs); degrades cleanly.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fis import visual, match

IMG_EXT = {".png", ".webp", ".jpg", ".jpeg"}
# aperture = perceptual-hash distance tolerance: tight = only near-identical
APERTURE = {"tight": 4, "normal": 10, "wide": 16}


def build_items(folder: str):
    items, docs, n_pdf = [], {}, 0
    for p in Path(folder).rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IMG_EXT:
            h = visual.phash_image(str(p))
            if h is not None:
                items.append(match.VisualItem(object_id="O-" + p.name, representation=ext.lstrip("."),
                                              phash=h, path=str(p)))
        elif ext == ".pdf":
            doc_id = f"D{n_pdf:03d}"; docs[doc_id] = str(p); n_pdf += 1
            for i, h in enumerate(visual.phash_pdf_pages(str(p)), start=1):
                items.append(match.VisualItem(object_id=f"{doc_id}-p{i}", representation="pdf_page",
                                              phash=h, page=i, document_id=doc_id))
    return items, docs


def main(argv):
    if not argv:
        print(__doc__); return 1
    folder = argv[0]
    aperture = next((a.split("=", 1)[1] for a in argv[1:] if a.startswith("--aperture=")), "tight")
    threshold = APERTURE.get(aperture, APERTURE["tight"])

    if not visual.available():
        print("Pillow not installed — run: pip install pillow pymupdf"); return 1

    out = Path("_atlas_out") / "visual" / Path(folder).name
    if out.exists():
        import shutil; shutil.rmtree(out)
    (out / "NOT_LOGGED").mkdir(parents=True, exist_ok=True)

    items, docs = build_items(folder)
    groups = match.build_groups(items, threshold=threshold)
    print(f"Scanned: {len(items)} visual objects ({len(docs)} PDFs) · aperture={aperture} (≤{threshold})")
    print(f"  {len(groups)} cross-format visual groups found")

    csv_path = out / "NOT_LOGGED" / "visual_groups.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["group_id", "member", "representation", "role", "points_to", "logged_to_master"])
        for g in groups:
            for m in g.manifest()["members"]:
                pts = f"{m.get('document','')} p{m.get('page','')}" if m["representation"] == "pdf_page" else m.get("path", "")
                w.writerow([g.group_id, m["object_id"], m["representation"], m["role"], pts, "no"])
    plan = match.stage_plan(groups, str(out))
    (out / "NOT_LOGGED" / "stage_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "source": folder, "objects": len(items), "pdfs": len(docs),
         "groups": len(groups), "logged_to_master": False,
         "note": "preview only; images copy, pdf pages become pointers, at act"}, indent=2), encoding="utf-8")
    for g in groups[:8]:
        reps = ",".join(sorted({m.representation for m in g.members}))
        print(f"    {g.group_id}: {len(g.members)} members [{reps}]")
    print(f"  -> {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
