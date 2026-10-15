"""04_ADAPT — legacy glossary cards -> mim.v1 stamp, mechanically.

The rule of thumb this tool enforces:
  if a script can do it without judgment, do it here, before the classifier.
  if it needs judgment (domain, ct-/ep- tags, standing off the closed list),
  it stays blank and goes through the Sidecar Review GUI + David.

What it does per card:
  stamps   sidecar: mim.v1, subject: <filename>, folder_class: glossary
  carries  source_file, and status -> standing ONLY if on the closed list
  derives  source: "[[<source_file basename, no extension>]]"
  keeps    every original field verbatim, nested lists and all
  leaves   the body below the closing --- untouched
  marks    adapted_from / adapted_at so the provenance is never in doubt

Originals are never touched. Output lands in 04_ADAPT/OUTBOX/<folder name>/.

    python adapt_cards.py "C:\\path\\to\\glossary folder"
    python adapt_cards.py "C:\\path\\to\\folder" "D:\\other\\outbox"
    ADAPT.bat   (drag a folder onto it, or run it and pick one)
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "03_CLASSIFY" / "02_CLASSIFICATION"))
sys.path.insert(0, str(REPO / "03_CLASSIFY" / "00_SHARED"))

from harness.adapters import sidecars  # noqa: E402
from taxonomy_validator import VALID_STANDING  # noqa: E402

# keys this tool writes itself — original blocks with these names are replaced
MANAGED = {"sidecar", "subject", "source", "source_file", "standing",
           "folder_class", "tags", "adapted_from", "adapted_at"}


def _split_blocks(fm_lines: list[str]) -> list[list[str]]:
    """Frontmatter lines -> one block per top-level key, continuations attached."""
    blocks: list[list[str]] = []
    for line in fm_lines:
        if ":" in line and not line.startswith((" ", "\t", "- ")):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    return blocks


def _block_value(block: list[str]) -> str:
    v = block[0].split(":", 1)[1]
    return v.split(" #")[0].strip().strip('"')


def convert_card_text(text: str, stem: str) -> str | None:
    """One legacy card -> mim.v1 text. None when there is no frontmatter at all."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None
    blocks = _split_blocks(lines[1:end])
    body = lines[end + 1:]

    old: dict[str, list[str]] = {}
    old_tags: list[str] = []
    for b in blocks:
        key = b[0].split(":", 1)[0].strip()
        if key == "tags":
            old_tags = [ln.strip()[2:].strip() for ln in b[1:]
                        if ln.strip().startswith("- ")]
        else:
            old[key] = b

    status = _block_value(old["status"]) if "status" in old else ""
    standing = status if status in VALID_STANDING else ""
    # older schema variant spells it file_path — same meaning, same translation
    source_file = next((_block_value(old[k]) for k in ("source_file", "file_path")
                        if k in old and _block_value(old[k])), "")
    source = Path(source_file).stem if source_file else ""

    out = [
        "---",
        "sidecar: mim.v1",
        f"subject: {stem}",
        f'source: "[[{source}]]"' if source else "source:",
        f'source_file: "{source_file}"' if source_file else "source_file:",
        f"standing: {standing}" if standing else "standing:",
        "folder_class: glossary",
        "tags:",
        "  - sidecar",
        "  - subject",
    ]
    seen = {"sidecar", "subject"}
    for t in old_tags:                       # legacy tags ride along, never guessed at
        if t not in seen:
            seen.add(t)
            out.append(f"  - {t}")
    out += [
        "adapted_from: glossary-card",
        f"adapted_at: {dt.datetime.now().isoformat(timespec='seconds')}",
    ]
    for key, block in old.items():           # everything else, verbatim
        if key not in MANAGED:
            out.extend(block)
    out.append("---")
    out.extend(body)
    return "\n".join(out)


def convert_folder(src: str | Path, dst: str | Path) -> dict:
    """Convert every convertible *.md in src into dst. Never writes to src."""
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    stats = {"converted": 0, "skipped": 0, "failed": [], "outbox": str(dst)}
    for p in sorted(src.glob("*.md")):
        try:
            if sidecars.parse_card(p)[0]:
                stats["skipped"] += 1
                print(f"  skip  {p.name}  (already mim.v1)")
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            out = convert_card_text(text, p.stem)
        except Exception as e:  # noqa: BLE001 — one bad card must not kill the run
            stats["failed"].append((p.name, f"{type(e).__name__}: {e}"))
            print(f"  FAIL  {p.name}  ({e})")
            continue
        if out is None:
            stats["failed"].append((p.name, "no frontmatter"))
            print(f"  FAIL  {p.name}  (no frontmatter)")
            continue
        (dst / p.name).write_text(out, encoding="utf-8")
        stats["converted"] += 1
        print(f"  ok    {p.name}")
    return stats


def main(argv: list[str]) -> int:
    src = Path(argv[1]) if len(argv) > 1 else None
    if src is None:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        picked = filedialog.askdirectory(title="Folder of legacy cards to adapt")
        if not picked:
            print("no folder picked — nothing done")
            return 1
        src = Path(picked)
    if not src.is_dir():
        print(f"not a folder: {src}")
        return 1
    dst = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent / "OUTBOX" / src.name
    print(f"adapting {src}\n   ->   {dst}\n")
    stats = convert_folder(src, dst)
    print(f"\ndone: {stats['converted']} converted, {stats['skipped']} already stamped, "
          f"{len(stats['failed'])} failed")
    for name, reason in stats["failed"]:
        print(f"  failed: {name} — {reason}")
    if stats["converted"]:
        print(f"\nnext: open the Sidecar Review GUI on {dst} and rule the blanks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
