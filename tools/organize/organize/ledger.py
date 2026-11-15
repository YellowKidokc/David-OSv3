"""Organize History Ledger — a lightweight, always-on file-move recorder.

It polls the folders you choose, compares snapshots, and writes a plain-text
record of every new file, rename, move, and delete. No external dependency:
just stdlib polling, so it runs anywhere the GUI does.

The record is JSON Lines inside a file with a custom ``.orgledger`` extension:
  * plain text — Notepad++ (or anything) opens it,
  * distinctive — the organizer is told to never move/sort ``.orgledger`` files,
  * append-only — with a "DO NOT DELETE" banner at the top.

Each watched folder gets its own ``_organize.orgledger`` logbook, and every
event is also appended to one central master ledger so you have a single
aggregated timeline.

CLI:
    python -m organize.ledger watch [--root DIR ...] [--interval 5] [--no-recursive]
    python -m organize.ledger tail [--root DIR] [-n 50]
    python -m organize.ledger aggregate [--root DIR ...]
    python -m organize.ledger install-startup [--root DIR ...] [--interval 5]
    python -m organize.ledger --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# fixed namespace so a given folder path always maps to the same UUID
FOLDER_NAMESPACE = uuid.UUID("6f1a0b2c-9d3e-5a47-8b1c-0e2f4a6c8d10")

LEDGER_EXT = ".orgledger"
LEDGER_NAME = "_organize" + LEDGER_EXT  # per-folder logbook file name
FIS_META = ".fis_meta.json"
DEFAULT_INTERVAL = 5.0
SNAPSHOT_CAP = 200_000  # safety cap on files walked per tick

BANNER = (
    "# Organize History Ledger — plain text (JSON Lines). Open it in Notepad++.\n"
    "# DO NOT DELETE. Each line below is one file event. The custom .orgledger\n"
    "# extension is excluded from organizing so cleanup never moves this file.\n"
)

# files we never record events for (our own logs, system noise, temp files)
_IGNORE_EXACT = {FIS_META, "thumbs.db", "desktop.ini", ".ds_store"}
_IGNORE_SUFFIX = (LEDGER_EXT, ".tmp", ".crdownload", ".partial", ".part")


def aggregate_dir() -> Path:
    return Path.home() / ".organize_gui" / "ledger"


def master_ledger_path() -> Path:
    return aggregate_dir() / ("master" + LEDGER_EXT)


def default_roots() -> List[str]:
    return [str(Path.home() / name) for name in ("Desktop", "Documents", "Downloads")]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def folder_uuid(folder: str) -> str:
    """Stable identity for a folder, derived from its absolute path."""
    try:
        resolved = str(Path(folder).expanduser().resolve()).lower()
    except OSError:
        resolved = str(Path(folder).expanduser()).lower()
    return str(uuid.uuid5(FOLDER_NAMESPACE, resolved))


def nlp_fingerprint(tokens: Iterable[str]) -> str:
    """A 'number' (UUID) summarising the NLP view of a folder's contents.

    Built from the sorted set of per-file signals (e.g. proposed names) so the
    same folder content yields the same fingerprint.
    """
    joined = "\n".join(sorted(str(t) for t in tokens if t))
    return str(uuid.uuid5(FOLDER_NAMESPACE, "nlp:" + joined))


def _ignored_name(name: str) -> bool:
    low = name.lower()
    if low in _IGNORE_EXACT:
        return True
    if name.startswith(".") or name.startswith("~$"):
        return True
    return low.endswith(_IGNORE_SUFFIX)


# --------------------------------------------------------------------------- #
# Snapshot + diff (pure, unit-testable)
# --------------------------------------------------------------------------- #
Snapshot = Dict[str, Tuple[int, int]]  # path -> (size, mtime)


def snapshot(roots: List[str], recursive: bool = True, cap: int = SNAPSHOT_CAP) -> Snapshot:
    snap: Snapshot = {}
    count = 0
    for root in roots:
        rp = Path(root).expanduser()
        if not rp.exists():
            continue
        iterator = rp.rglob("*") if recursive else rp.iterdir()
        for item in iterator:
            if count >= cap:
                return snap
            try:
                if item.is_dir():
                    continue
                if _ignored_name(item.name):
                    continue
                st = item.stat()
            except OSError:
                continue
            snap[str(item)] = (st.st_size, int(st.st_mtime))
            count += 1
    return snap


def _event(kind: str, *, ts: str, frm: Optional[str], to: Optional[str], certain: bool) -> dict:
    from_dir = str(Path(frm).parent) if frm else None
    to_dir = str(Path(to).parent) if to else None
    old_name = Path(frm).name if frm else None
    new_name = Path(to).name if to else None
    name = new_name or old_name
    ev = {
        "ts": ts,
        "event": kind,
        "file": name,
        "from": from_dir,
        "to": to_dir,
        "certain": certain,
    }
    if old_name and new_name and old_name != new_name:
        ev["old_name"] = old_name
        ev["new_name"] = new_name
    return ev


def diff_snapshots(old: Snapshot, new: Snapshot, ts: Optional[str] = None) -> List[dict]:
    """Compare two snapshots and infer new/rename/move/delete events.

    Moves and renames are reconstructed by correlating a disappeared path with
    an appeared path of the same size. Same name + different folder = a clean
    move (certain). Different name = an inferred move/rename (certain=False).
    """
    ts = ts or now_iso()
    added = [p for p in new if p not in old]
    removed = [p for p in old if p not in new]

    used_removed = set()
    events: List[dict] = []

    def name_key(path: str, size: int) -> Tuple[str, int]:
        return (Path(path).name.lower(), size)

    removed_by_namesize: Dict[Tuple[str, int], List[str]] = {}
    removed_by_size: Dict[int, List[str]] = {}
    for p in removed:
        size = old[p][0]
        removed_by_namesize.setdefault(name_key(p, size), []).append(p)
        removed_by_size.setdefault(size, []).append(p)

    leftover_added: List[str] = []
    for a in sorted(added):
        a_size = new[a][0]
        match = None
        certain = True

        # 1) exact same filename + size -> clean move
        for cand in removed_by_namesize.get(name_key(a, a_size), []):
            if cand not in used_removed:
                match = cand
                break
        # 2) same size, different name -> inferred move/rename
        if match is None:
            for cand in removed_by_size.get(a_size, []):
                if cand not in used_removed and Path(cand).name.lower() != Path(a).name.lower():
                    match = cand
                    certain = False
                    break

        if match is None:
            leftover_added.append(a)
            continue

        used_removed.add(match)
        from_dir = str(Path(match).parent)
        to_dir = str(Path(a).parent)
        if from_dir == to_dir:
            events.append(_event("rename", ts=ts, frm=match, to=a, certain=True))
        else:
            events.append(_event("move", ts=ts, frm=match, to=a, certain=certain))

    for a in leftover_added:
        events.append(_event("new", ts=ts, frm=None, to=a, certain=True))
    for p in removed:
        if p not in used_removed:
            events.append(_event("delete", ts=ts, frm=p, to=None, certain=True))
    return events


# --------------------------------------------------------------------------- #
# Ledger writing / reading
# --------------------------------------------------------------------------- #
class LedgerWriter:
    def __init__(self, per_folder: bool = True, master_path: Optional[Path] = None) -> None:
        self.per_folder = per_folder
        self.master_path = Path(master_path) if master_path else master_ledger_path()

    def write(self, events: List[dict]) -> None:
        for ev in events:
            line = json.dumps(ev, ensure_ascii=False)
            self._append(self.master_path, line, BANNER)
            if self.per_folder:
                folder = ev.get("to") or ev.get("from")
                if folder:
                    header = BANNER + f"# folder_uuid: {folder_uuid(folder)}\n"
                    self._append(Path(folder) / LEDGER_NAME, line, header)

    @staticmethod
    def _append(path: Path, line: str, header: str) -> None:
        try:
            is_new = not path.exists()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                if is_new:
                    fh.write(header)
                fh.write(line + "\n")
        except OSError:
            pass  # never let a logging failure break the watcher


def record_folder_fingerprint(
    folder: str,
    fingerprint: str,
    n_files: int,
    process: str,
    writer: Optional[LedgerWriter] = None,
) -> dict:
    """Write the folder's NLP 'number' (and UUID) onto its paper + the master."""
    writer = writer or LedgerWriter()
    ev = {
        "ts": now_iso(),
        "event": "folder_fingerprint",
        "file": Path(folder).name,
        "from": None,
        "to": str(folder),
        "certain": True,
        "folder_uuid": folder_uuid(folder),
        "nlp_fingerprint": fingerprint,
        "files": n_files,
        "process": process,
    }
    writer.write([ev])
    return ev


def read_folder_uuid(path: Path) -> Optional[str]:
    path = Path(path)
    if not path.exists():
        return None
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if raw.startswith("# folder_uuid:"):
                return raw.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def read_events(path: Path, limit: int = 500) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    out: List[dict] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out[-limit:]


def aggregate(roots: List[str]) -> Path:
    """Rebuild the master ledger by merging every per-folder ledger found."""
    seen = set()
    merged: List[dict] = []
    for root in roots:
        rp = Path(root).expanduser()
        if not rp.exists():
            continue
        for ledger in rp.rglob(LEDGER_NAME):
            for ev in read_events(ledger, limit=10_000_000):
                key = json.dumps(ev, sort_keys=True, ensure_ascii=False)
                if key not in seen:
                    seen.add(key)
                    merged.append(ev)
    merged.sort(key=lambda e: e.get("ts", ""))
    master = master_ledger_path()
    master.parent.mkdir(parents=True, exist_ok=True)
    with open(master, "w", encoding="utf-8") as fh:
        fh.write(BANNER)
        for ev in merged:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return master


# --------------------------------------------------------------------------- #
# Watcher
# --------------------------------------------------------------------------- #
class LedgerWatcher:
    def __init__(
        self,
        roots: List[str],
        interval: float = DEFAULT_INTERVAL,
        recursive: bool = True,
        writer: Optional[LedgerWriter] = None,
    ) -> None:
        self.roots = list(roots)
        self.interval = interval
        self.recursive = recursive
        self.writer = writer or LedgerWriter()
        self.prev: Snapshot = snapshot(self.roots, self.recursive)

    def tick(self) -> List[dict]:
        current = snapshot(self.roots, self.recursive)
        events = diff_snapshots(self.prev, current)
        if events:
            self.writer.write(events)
        self.prev = current
        return events

    def run_forever(self, stop_event: Optional[threading.Event] = None) -> None:
        while not (stop_event and stop_event.is_set()):
            time.sleep(self.interval)
            try:
                self.tick()
            except Exception:
                pass  # keep watching even if one tick hiccups


# --------------------------------------------------------------------------- #
# Startup install + editor helper
# --------------------------------------------------------------------------- #
def startup_dir() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def install_startup(roots: List[str], interval: float, python_exe: Optional[str] = None) -> Path:
    python_exe = python_exe or sys.executable
    roots_args = " ".join(f'--root "{r}"' for r in roots)
    bat = startup_dir() / "organize-history-watcher.bat"
    bat.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "@echo off\r\n"
        "set PYTHONUTF8=1\r\n"
        "set PYTHONIOENCODING=utf-8\r\n"
        f'start "" /min "{python_exe}" -m organize.ledger watch {roots_args} --interval {interval}\r\n'
    )
    bat.write_text(content, encoding="utf-8")
    return bat


def uninstall_startup() -> bool:
    bat = startup_dir() / "organize-history-watcher.bat"
    if bat.exists():
        bat.unlink()
        return True
    return False


def open_in_editor(path: Path) -> None:
    path = str(path)
    for editor in ("notepad++.exe", "notepad.exe"):
        try:
            subprocess.Popen([editor, path])
            return
        except OSError:
            continue
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cmd_watch(args) -> None:
    roots = args.root or default_roots()
    watcher = LedgerWatcher(roots, interval=args.interval, recursive=not args.no_recursive)
    print(f"Watching {len(roots)} folder(s) every {args.interval}s. Master ledger: {master_ledger_path()}")
    for root in roots:
        print(f"  - {root}")
    try:
        watcher.run_forever()
    except KeyboardInterrupt:
        print("Stopped.")


def _cmd_tail(args) -> None:
    path = Path(args.root) / LEDGER_NAME if args.root else master_ledger_path()
    for ev in read_events(path, limit=args.n):
        print(json.dumps(ev, ensure_ascii=False))


def _cmd_aggregate(args) -> None:
    roots = args.root or default_roots()
    master = aggregate(roots)
    print(f"Aggregated into {master}")


def _cmd_install_startup(args) -> None:
    roots = args.root or default_roots()
    bat = install_startup(roots, args.interval)
    print(f"Installed startup watcher: {bat}")


def _self_test() -> None:
    import tempfile
    import shutil

    base = Path(tempfile.mkdtemp(prefix="ledger_test_"))
    desk = base / "Desk"
    docs = base / "Docs" / "Excel"
    desk.mkdir(parents=True)
    docs.mkdir(parents=True)

    (desk / "budget.xlsx").write_text("x", encoding="utf-8")
    (desk / "photo.jpg").write_text("yyyy", encoding="utf-8")
    roots = [str(desk), str(base / "Docs")]

    writer = LedgerWriter(per_folder=True, master_path=base / "master.orgledger")
    watcher = LedgerWatcher(roots, writer=writer)

    # clean move: budget.xlsx Desk -> Docs/Excel (same name, same size)
    (desk / "budget.xlsx").rename(docs / "budget.xlsx")
    # rename in place
    (desk / "photo.jpg").rename(desk / "vacation.jpg")
    # brand new file
    (desk / "notes.txt").write_text("hello", encoding="utf-8")

    events = watcher.tick()
    kinds = {e["event"] for e in events}
    by_kind = {e["event"]: e for e in events}
    assert "move" in kinds, f"expected a move, got {events}"
    assert by_kind["move"]["file"] == "budget.xlsx" and by_kind["move"]["certain"] is True
    assert by_kind["move"]["to"].endswith("Excel")
    assert "rename" in kinds, f"expected a rename, got {events}"
    assert by_kind["rename"].get("new_name") == "vacation.jpg"
    assert "new" in kinds, f"expected a new file, got {events}"
    print(f"OK ledger diff: {sorted(kinds)}")

    # the .orgledger is excluded from being recorded (no feedback loop)
    follow = watcher.tick()
    assert all(not (e.get("file") or "").endswith(LEDGER_EXT) for e in follow), follow
    print("OK ledger ignores its own .orgledger writes")

    # per-folder logbook exists, plain text, banner + JSON lines
    book = docs / LEDGER_NAME
    assert book.exists(), "per-folder ledger missing"
    text = book.read_text(encoding="utf-8")
    assert text.startswith("# Organize History Ledger"), "banner missing"
    assert read_events(book), "no events read back"
    print("OK per-folder logbook written, banner present, readable")

    # delete detection
    (docs / "budget.xlsx").unlink()
    del_events = watcher.tick()
    assert any(e["event"] == "delete" and e["file"] == "budget.xlsx" for e in del_events), del_events
    print("OK ledger delete detection")

    # folder identity: stable UUID stamped in the paper, plus NLP fingerprint
    uid = folder_uuid(str(docs))
    assert uid == folder_uuid(str(docs)), "folder UUID not stable"
    assert read_folder_uuid(book) == uid, "folder_uuid not stamped in paper header"
    fp = nlp_fingerprint(["alpha_FIN_1.pdf", "beta_OPS_2.pdf"])
    assert fp == nlp_fingerprint(["beta_OPS_2.pdf", "alpha_FIN_1.pdf"]), "fingerprint not order-stable"
    rec = record_folder_fingerprint(str(docs), fp, 2, "File Intelligence", writer=writer)
    assert rec["folder_uuid"] == uid and rec["nlp_fingerprint"] == fp
    assert any(e.get("event") == "folder_fingerprint" for e in read_events(book)), "fingerprint not on paper"
    print("OK folder UUID + NLP fingerprint on the paper")

    shutil.rmtree(base, ignore_errors=True)
    print("ledger self-test passed")


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        _self_test()
        return

    parser = argparse.ArgumentParser(prog="organize.ledger")
    sub = parser.add_subparsers(dest="command")

    p_watch = sub.add_parser("watch", help="watch folders and record events")
    p_watch.add_argument("--root", action="append", help="folder to watch (repeatable)")
    p_watch.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    p_watch.add_argument("--no-recursive", action="store_true")
    p_watch.set_defaults(func=_cmd_watch)

    p_tail = sub.add_parser("tail", help="print recent ledger events")
    p_tail.add_argument("--root", help="a watched folder (default: master ledger)")
    p_tail.add_argument("-n", type=int, default=50)
    p_tail.set_defaults(func=_cmd_tail)

    p_agg = sub.add_parser("aggregate", help="rebuild master ledger from per-folder logs")
    p_agg.add_argument("--root", action="append")
    p_agg.set_defaults(func=_cmd_aggregate)

    p_start = sub.add_parser("install-startup", help="run the watcher at login")
    p_start.add_argument("--root", action="append")
    p_start.add_argument("--interval", type=float, default=DEFAULT_INTERVAL)
    p_start.set_defaults(func=_cmd_install_startup)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
