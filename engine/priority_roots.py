"""High-priority places — declare them once, and every scan respects them.

Three modes per root:

  ``skip``    never walked, never read. Use for live sites, .git, huge caches.
  ``flag``    walked, but everything found there is marked high priority, and any
              file taken out of it carries that provenance into the report.
  ``protect`` walked and readable, but no write may land inside it
              (delegates to path_write_policy).

The registry lives in ``config/priority_roots.json`` so the GUI, the scanners and
any later job read the same list. Generic: nothing here knows about a particular
folder, and a root may be a drive, a share or a single file.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import path_write_policy

MODES = ("skip", "flag", "protect")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "priority_roots.json"

DEFAULT_SKIP_NAMES = (".git", ".lake", "node_modules", "__pycache__", ".venv", "$RECYCLE.BIN")


@dataclass(frozen=True)
class PriorityRoot:
    path: str
    mode: str = "flag"
    label: str = ""
    note: str = ""

    @property
    def resolved(self) -> Path:
        return Path(self.path).expanduser()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalise(path: str | Path) -> str:
    return str(Path(path).expanduser()).rstrip("\\/").lower()


def load(config: str | Path | None = None) -> list[PriorityRoot]:
    file = Path(config or CONFIG)
    if not file.exists():
        return []
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = raw.get("roots", raw) if isinstance(raw, dict) else raw
    out = []
    for entry in entries:
        if isinstance(entry, str):
            out.append(PriorityRoot(entry))
        elif isinstance(entry, dict) and entry.get("path"):
            mode = str(entry.get("mode", "flag")).lower()
            out.append(PriorityRoot(str(entry["path"]), mode if mode in MODES else "flag",
                                    str(entry.get("label", "")), str(entry.get("note", ""))))
    return out


def save(roots: list[PriorityRoot], config: str | Path | None = None) -> Path:
    file = Path(config or CONFIG)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"roots": [r.to_dict() for r in roots]}, indent=2), encoding="utf-8")
    return file


def add(path: str | Path, mode: str = "flag", label: str = "", note: str = "",
        config: str | Path | None = None) -> list[PriorityRoot]:
    roots = [r for r in load(config) if _normalise(r.path) != _normalise(path)]
    roots.append(PriorityRoot(str(Path(path).expanduser()), mode if mode in MODES else "flag", label, note))
    save(roots, config)
    return roots


def remove(path: str | Path, config: str | Path | None = None) -> list[PriorityRoot]:
    roots = [r for r in load(config) if _normalise(r.path) != _normalise(path)]
    save(roots, config)
    return roots


def _under(candidate: Path, root: Path) -> bool:
    text, root_text = _normalise(candidate), _normalise(root)
    return text == root_text or text.startswith(root_text + "\\") or text.startswith(root_text + "/")


def classify(path: str | Path, roots: list[PriorityRoot] | None = None) -> PriorityRoot | None:
    """Which declared root, if any, governs *path*. Deepest match wins."""
    candidate = Path(path).expanduser()
    matches = [r for r in (roots if roots is not None else load()) if _under(candidate, r.resolved)]
    return max(matches, key=lambda r: len(_normalise(r.path))) if matches else None


def is_skipped(path: str | Path, roots: list[PriorityRoot] | None = None) -> bool:
    found = classify(path, roots)
    if found and found.mode == "skip":
        return True
    return any(part in DEFAULT_SKIP_NAMES for part in Path(path).parts)


def is_high_priority(path: str | Path, roots: list[PriorityRoot] | None = None) -> bool:
    found = classify(path, roots)
    return bool(found and found.mode in {"flag", "protect"})


def provenance(path: str | Path, roots: list[PriorityRoot] | None = None) -> dict[str, object]:
    """Stamp for a report row: where it came from and whether that place is sensitive."""
    found = classify(path, roots)
    return {
        "path": str(path),
        "high_priority": bool(found and found.mode in {"flag", "protect"}),
        "priority_root": found.path if found else None,
        "priority_label": found.label if found else None,
        "priority_mode": found.mode if found else None,
    }


def apply_write_protection(roots: list[PriorityRoot] | None = None) -> list[str]:
    """Push every ``protect`` root into the write policy for this process."""
    applied = []
    for root in (roots if roots is not None else load()):
        if root.mode == "protect":
            path_write_policy.protect_root(root.resolved)
            applied.append(str(root.resolved))
    return applied


def walk_filter(roots: list[PriorityRoot] | None = None):
    """Predicate for os.walk / rglob consumers: True when the path may be visited."""
    declared = roots if roots is not None else load()

    def allowed(path: str | Path) -> bool:
        return not is_skipped(path, declared)

    return allowed
