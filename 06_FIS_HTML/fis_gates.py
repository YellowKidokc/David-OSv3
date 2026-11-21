"""FIS safety gates 1-5. Standard library only.

Gate 1  disk space      check_space()
Gate 2  built sets      is_built_set(), frontmatter path check
Gate 3  Obsidian files  is_protected()
Gate 4  simulate/move   simulate() -> receipt, apply_receipt() -> undo, undo()
Gate 5  one page        lane_for(), page_report()

CLI:
  python fis_gates.py simulate <folder>          writes a receipt, moves nothing
  python fis_gates.py apply <receipt.json>       moves, writes undo file
  python fis_gates.py undo <undo.json>           puts files back
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

DATA_DIR = ".data"
OBSIDIAN_PAGE = "OBSIDIAN_REGISTRY.html"
FIS_PAGE = "FIS.html"
GENERATED_PAGES = {OBSIDIAN_PAGE, FIS_PAGE}
MOVE_EXTS = {".json", ".xlsx", ".xls", ".xlsm", ".csv", ".html", ".htm"}
PROTECTED_DIRS = {".obsidian", ".git", ".trash", DATA_DIR}
PROTECTED_EXTS = {".base", ".canvas"}
BUILT_SET_NAMES = ("50_PRODUCTION_AND_PUBLICATION", "axiom", "site", "_site", "dist", "build", "public")
PATH_FIELDS = ("card", "receipt")
MIN_FREE_GB = 2.0
LISTING_CAP = 2000


class GateError(RuntimeError):
    pass


# ---- Gate 1 -------------------------------------------------------------
def free_gb(path: Path) -> float:
    return shutil.disk_usage(Path(path).anchor or path).free / 1024**3


def check_space(path: Path, need_bytes: int = 0, min_gb: float = MIN_FREE_GB) -> None:
    free = free_gb(path)
    if free * 1024**3 - need_bytes < min_gb * 1024**3:
        raise GateError(f"Gate 1: {Path(path).anchor} has {free:.2f} GB free; need {min_gb} GB + {need_bytes/1024**2:.1f} MB. Stopped, nothing written.")


# ---- Gate 3 -------------------------------------------------------------
def is_protected(p: Path, root: Path | None = None) -> bool:
    parts = p.relative_to(root).parts if root else p.parts
    return any(part in PROTECTED_DIRS for part in parts) or p.suffix.lower() in PROTECTED_EXTS


# ---- Gate 2 -------------------------------------------------------------
_HREF = re.compile(r'(?:href|src)\s*=\s*["\']([^"\'#?]+)', re.I)


def is_built_set(folder: Path, root: Path | None = None) -> bool:
    """A folder whose HTML pages link to sibling files is a built set: never split it."""
    parts = folder.relative_to(root).parts if root else folder.parts
    if any(n.lower() in part.lower() for part in parts for n in BUILT_SET_NAMES):
        return True
    for html in list(folder.glob("*.htm*"))[:50]:
        if html.name in GENERATED_PAGES:
            continue
        try:
            text = html.read_text("utf-8", errors="ignore")[:200_000]
        except OSError:
            continue
        for ref in _HREF.findall(text):
            if "://" in ref or ref.startswith(("/", "data:", "mailto:")):
                continue
            if (folder / ref).exists():
                return True
    return False


def frontmatter_paths(md: Path) -> dict[str, str]:
    try:
        text = md.read_text("utf-8", errors="ignore")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"\s*(\w+)\s*:\s*['\"]?([^'\"]+?)['\"]?\s*$", line)
        if m and m.group(1) in PATH_FIELDS:
            out[m.group(1)] = m.group(2)
    return out


def broken_refs_after(folder: Path, moves: list[dict]) -> list[dict]:
    """Frontmatter paths that point at a file being moved get flagged for rewrite."""
    moved = {Path(m["src"]).resolve(): m["dst"] for m in moves}
    issues = []
    for md in folder.glob("*.md"):
        for field, ref in frontmatter_paths(md).items():
            target = (md.parent / ref).resolve()
            if target in moved:
                new = os.path.relpath(moved[target], md.parent).replace("\\", "/")
                issues.append({"note": str(md), "field": field, "old": ref, "new": new})
    return issues


# ---- Gate 5 -------------------------------------------------------------
def lane_for(folder: Path) -> str:
    for p in [folder, *folder.parents]:
        if (p / ".obsidian").is_dir():
            return "obsidian"
    return "fis"


def page_report(folder: Path) -> dict:
    lane = lane_for(folder)
    page = OBSIDIAN_PAGE if lane == "obsidian" else FIS_PAGE
    extra = [n for n in GENERATED_PAGES - {page} if (folder / n).exists()]
    return {"lane": lane, "page": page, "extra_pages_found": extra}


# ---- Gate 4 -------------------------------------------------------------
def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def simulate(root: Path, out_dir: Path | None = None) -> Path:
    root = Path(root).resolve()
    moves, skipped, refs, pages = [], [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        dirnames[:] = [n for n in dirnames if n not in PROTECTED_DIRS]
        rep = page_report(d)
        if rep["extra_pages_found"]:
            pages.append({"folder": str(d), **rep})
        if is_built_set(d, root):
            skipped.append({"folder": str(d), "reason": "built set (gate 2)"})
            continue
        folder_moves = []
        for name in filenames[:LISTING_CAP]:
            p = d / name
            if is_protected(p, root):
                continue
            if p.suffix.lower() in MOVE_EXTS and name not in GENERATED_PAGES:
                dst = d / DATA_DIR / name
                if dst.exists():
                    skipped.append({"file": str(p), "reason": "already in .data"})
                    continue
                folder_moves.append({"src": str(p), "dst": str(dst), "sha256": sha256(p), "bytes": p.stat().st_size})
        if len(filenames) > LISTING_CAP:
            skipped.append({"folder": str(d), "reason": f"capped at {LISTING_CAP} of {len(filenames)} files"})
        refs += broken_refs_after(d, folder_moves)
        moves += folder_moves
    receipt = {
        "kind": "fis-move-receipt", "mode": "simulation", "root": str(root),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "free_gb": round(free_gb(root), 2),
        "moves": moves, "skipped": skipped, "frontmatter_rewrites": refs, "page_conflicts": pages,
        "totals": {"files": len(moves), "bytes": sum(m["bytes"] for m in moves)},
    }
    out_dir = Path(out_dir or Path(__file__).parent / "receipts")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"receipt_{root.name}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(receipt, indent=2), "utf-8")
    return out


def _rewrite_ref(note: Path, field: str, old: str, new: str) -> None:
    text = note.read_text("utf-8")
    text = re.sub(rf"(^\s*{field}\s*:\s*['\"]?){re.escape(old)}", lambda m: m.group(1) + new, text, count=1, flags=re.M)
    note.write_text(text, "utf-8")


def apply_receipt(receipt_path: Path) -> Path:
    r = json.loads(Path(receipt_path).read_text("utf-8"))
    check_space(Path(r["root"]), need_bytes=1024**2)  # moves are same-drive renames
    done = []
    undo_path = Path(receipt_path).with_name(Path(receipt_path).stem.replace("receipt_", "undo_") + ".json")
    try:
        for m in r["moves"]:
            src, dst = Path(m["src"]), Path(m["dst"])
            if not src.exists():
                raise GateError(f"Gate 4: {src} is gone since simulation (moved elsewhere?). Stopped; re-simulate.")
            if sha256(src) != m["sha256"]:
                raise GateError(f"Gate 4: {src} changed since simulation. Stopped; re-simulate.")
            if dst.exists():
                raise GateError(f"Gate 4: {dst} already exists. Stopped.")
            dst.parent.mkdir(exist_ok=True)
            os.replace(src, dst)
            done.append({"src": str(src), "dst": str(dst), "sha256": m["sha256"]})
        for fx in r["frontmatter_rewrites"]:
            _rewrite_ref(Path(fx["note"]), fx["field"], fx["old"], fx["new"])
            done.append({"rewrite": fx})
    finally:
        undo_path.write_text(json.dumps({"kind": "fis-undo", "from": str(receipt_path), "done": done}, indent=2), "utf-8")
    return undo_path


def undo(undo_path: Path) -> int:
    u = json.loads(Path(undo_path).read_text("utf-8"))
    n = 0
    for step in reversed(u["done"]):
        if "rewrite" in step:
            fx = step["rewrite"]
            _rewrite_ref(Path(fx["note"]), fx["field"], fx["new"], fx["old"])
        else:
            src, dst = Path(step["src"]), Path(step["dst"])
            if dst.exists() and not src.exists():
                os.replace(dst, src)
                n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in {"simulate", "apply", "undo"}:
        sys.exit(__doc__)
    cmd, arg = sys.argv[1], Path(sys.argv[2])
    try:
        if cmd == "simulate":
            out = simulate(arg)
            t = json.loads(out.read_text("utf-8"))
            print(f"Receipt: {out}\n  would move {t['totals']['files']} files, skip {len(t['skipped'])}, "
                  f"rewrite {len(t['frontmatter_rewrites'])} frontmatter refs, {len(t['page_conflicts'])} page conflicts")
        elif cmd == "apply":
            print(f"Moved. Undo file: {apply_receipt(arg)}")
        else:
            print(f"Restored {undo(arg)} files.")
    except GateError as e:
        sys.exit(str(e))
