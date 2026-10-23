"""Canon pins — mark whole folders as a class (e.g. every file in 21_AXIOM NODES
is a CANON axiom). Pinned files always appear in searches for that term, ranked
above everything else, and carry the pinned level/status into their sidecars.

Registry: gui/canon_pins.json   (also remembers recently used folders)
  python canon_pins.py list
  python canon_pins.py add "<folder>" axiom --level CANON --status PUBLISHED
  python canon_pins.py remove "<folder>"
  python canon_pins.py which "<file>"
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent / "canon_pins.json"
PIN_BOOST = 1000          # added to rank so pinned files always sort first
MAX_RECENT = 15


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p)).rstrip("\\/")


def load() -> dict:
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pins": [], "recent_folders": []}


def save(reg: dict) -> None:
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def add_pin(folder: str, term: str, code: str, level: str = "CANON", status: str = "PUBLISHED",
            note: str = "") -> dict:
    reg = load()
    reg["pins"] = [p for p in reg["pins"] if not (_norm(p["folder"]) == _norm(folder) and p["term"].lower() == term.lower())]
    pin = {"folder": str(Path(folder)), "term": term, "code": code, "level": level, "status": status,
           "note": note, "added": datetime.now().isoformat(timespec="seconds")}
    reg["pins"].append(pin)
    save(reg)
    remember_folder(folder)
    return pin


def remove_pin(folder: str, term: str | None = None) -> int:
    reg = load()
    before = len(reg["pins"])
    reg["pins"] = [p for p in reg["pins"]
                   if not (_norm(p["folder"]) == _norm(folder) and (term is None or p["term"].lower() == term.lower()))]
    save(reg)
    return before - len(reg["pins"])


def remember_folder(folder: str) -> None:
    reg = load()
    rec = [f for f in reg.get("recent_folders", []) if _norm(f) != _norm(folder)]
    reg["recent_folders"] = [str(Path(folder))] + rec[: MAX_RECENT - 1]
    save(reg)


def pins_for_term(term: str, synonyms: list[str] = ()) -> list[dict]:
    names = {term.lower().strip()} | {s.lower().strip() for s in synonyms}
    names |= {n.rstrip("s") for n in names}
    return [p for p in load()["pins"] if p["term"].lower().rstrip("s") in names]


def pin_for_path(path: str, pins: list[dict]) -> dict | None:
    """Most specific (deepest) pin whose folder contains path."""
    np = _norm(path)
    best = None
    for p in pins:
        f = _norm(p["folder"])
        if np == f or np.startswith(f + os.sep):
            if best is None or len(f) > len(_norm(best["folder"])):
                best = p
    return best


_FM_KEYS = ("canonical_id", "legacy_id", "title", "status")


def frontmatter_ids(text: str) -> dict:
    """Pull a few identity keys from YAML frontmatter, if present."""
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out = {}
    for k in _FM_KEYS:
        km = re.search(rf'^{k}:\s*"?([^"\n]*)"?\s*$', m.group(1), re.M)
        if km:
            out[k] = km.group(1).strip()
    return out


def _cli(argv):
    if not argv or argv[0] == "list":
        reg = load()
        for p in reg["pins"]:
            print(f"[{p['code']}] {p['term']:<16} {p['level']:<10} {p['status']:<10} {p['folder']}")
        print(f"{len(reg['pins'])} pins · registry {REGISTRY}")
    elif argv[0] == "add" and len(argv) >= 3:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("folder"); ap.add_argument("term")
        ap.add_argument("--code", default=None); ap.add_argument("--level", default="CANON")
        ap.add_argument("--status", default="PUBLISHED")
        a = ap.parse_args(argv[1:])
        code = a.code or ("AX" if a.term.lower().startswith("axiom") else a.term[:2].upper())
        print(add_pin(a.folder, a.term, code, a.level, a.status))
    elif argv[0] == "remove" and len(argv) >= 2:
        print(f"removed {remove_pin(argv[1])}")
    elif argv[0] == "which" and len(argv) >= 2:
        print(pin_for_path(argv[1], load()["pins"]))
    else:
        print(__doc__)


if __name__ == "__main__":
    _cli(sys.argv[1:])
