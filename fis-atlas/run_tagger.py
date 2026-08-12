#!/usr/bin/env python3
"""Tagger runner — familiarize on a corpus, discover tag-words, test the API.

    python run_tagger.py "<folder>" [--seeds god,lord] [--out _atlas_out/tagger]

Read-only over the source. Writes a CSV of discovered associations, tries the
local model (Ollama) for the "names of God" (API test), and STAGES everything
into NOT_LOGGED/ (since the master lexicon isn't updated yet) with a manifest,
plus an empty LOGGED_TO_MASTER/ — so anything not yet in the master can be
deleted safely by folder.
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fis import corpus_learn

SEED_LEXICON = {
    "GOD": ["god", "lord", "yahweh", "elohim", "almighty"],
    "CHARACTER_OF_GOD": ["holy", "righteous", "just", "merciful", "faithful",
                         "sovereign", "love", "grace", "goodness", "wrath"],
}


def read_docs(folder: str, exts=(".md", ".txt", ".html")) -> list[str]:
    docs = []
    for p in Path(folder).rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            try:
                docs.append(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return docs


def ollama_names_of_god(timeout=30) -> dict:
    """API test: ask the local model for the names of God. Honest about failure."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1) as r:
            if r.status != 200:
                return {"api": "unreachable", "names": []}
    except Exception:
        return {"api": "not_installed", "names": [],
                "note": "Ollama not reachable at localhost:11434 — run `ollama pull llama3.2`"}
    try:
        prompt = ("List distinct names/titles of God from Scripture and theology. "
                  'Return ONLY JSON: {"names": ["...", "..."]}')
        payload = json.dumps({"model": "llama3.2", "prompt": prompt, "stream": False,
                              "format": "json", "options": {"temperature": 0}}).encode()
        req = urllib.request.Request("http://localhost:11434/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode())
        parsed = json.loads(out.get("response", "{}"))
        return {"api": "ok", "names": parsed.get("names", []), "tier": "inferred"}
    except Exception as e:
        return {"api": f"error: {type(e).__name__}", "names": []}


def main(argv):
    if not argv:
        print(__doc__); return 1
    folder = argv[0]
    out_root = Path("_atlas_out") / "tagger" / Path(folder).name
    (out_root / "NOT_LOGGED").mkdir(parents=True, exist_ok=True)
    (out_root / "LOGGED_TO_MASTER").mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    docs = read_docs(folder)
    print(f"Corpus: {len(docs)} readable files from {folder}")

    proposals = corpus_learn.familiarize(SEED_LEXICON, docs, min_count=2, top=40)

    # write associations CSV into NOT_LOGGED (not yet in the master lexicon)
    csv_path = out_root / "NOT_LOGGED" / "associations.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["category", "term", "co_count", "lift", "tier", "logged_to_master"])
        for cat, rows in proposals.items():
            for term, co, lift in rows:
                w.writerow([cat, term, co, lift, "inferred", "no"])
    print(f"  associations -> {csv_path}")
    for cat, rows in proposals.items():
        top = ", ".join(t for t, _, _ in rows[:8])
        print(f"    {cat}: {top}")

    # API test: names of God
    names = ollama_names_of_god()
    (out_root / "NOT_LOGGED" / "names_of_god.json").write_text(
        json.dumps(names, indent=2), encoding="utf-8")
    print(f"  API test (names of God): {names['api']}"
          + (f" — {len(names['names'])} names" if names.get("names") else ""))

    manifest = {
        "generated_at": stamp, "source": folder, "corpus_files": len(docs),
        "outputs": ["NOT_LOGGED/associations.csv", "NOT_LOGGED/names_of_god.json"],
        "logged_to_master": False,
        "note": "Master lexicon not updated yet. Everything here is deletable by "
                "removing NOT_LOGGED/. On approval, promote rows to LOGGED_TO_MASTER/.",
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  manifest -> {out_root/'manifest.json'}  (logged_to_master=False)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
