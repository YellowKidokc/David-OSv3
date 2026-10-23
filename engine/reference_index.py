"""Reference index — who points at whom, and repointing them when files move.

Generic over any tree of HTML, Markdown, CSS or JSON: build the index once, then
ask what breaks if a path moves, or rewrite the referrers after it moved. The
rename planner and the file action worker both use this; nothing here is
site-specific.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

SCANNABLE = {".html", ".htm", ".md", ".markdown", ".css", ".json", ".js"}

PATTERNS = (
    re.compile(r"""(?:href|src|data-src|poster|action)\s*=\s*["']([^"'#?]+)["']""", re.I),  # html
    re.compile(r"""\]\(\s*<?([^)\s>"']+)>?(?:\s+["'][^)]*["'])?\s*\)"""),                     # markdown
    re.compile(r"""url\(\s*["']?([^)"']+)["']?\s*\)""", re.I),                                # css
    re.compile(r"""\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]"""),                                     # wiki links
)

EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#|mailto:|data:)", re.I)


@dataclass
class ReferenceIndex:
    root: Path
    outgoing: dict[Path, list[tuple[str, Path | None]]] = field(default_factory=lambda: defaultdict(list))
    incoming: dict[Path, list[Path]] = field(default_factory=lambda: defaultdict(list))
    broken: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def referenced(self) -> set[Path]:
        return {target for target in self.incoming if target.exists()}

    def referrers(self, target: str | Path) -> list[Path]:
        return list(self.incoming.get(Path(target).resolve(), []))

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "files_scanned": len(self.outgoing),
            "targets": len(self.incoming),
            "broken": [{"from": str(src), "ref": ref} for src, ref in self.broken],
            "incoming": {str(k): [str(p) for p in v] for k, v in self.incoming.items()},
        }

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return out


def _candidates(text: str) -> list[str]:
    found: list[str] = []
    for pattern in PATTERNS:
        found.extend(match.group(1).strip() for match in pattern.finditer(text))
    return [ref for ref in found if ref and not EXTERNAL.match(ref)]


def _resolve(source: Path, ref: str, root: Path) -> Path | None:
    cleaned = unquote(urlparse(ref).path).replace("\\", "/").strip()
    if not cleaned:
        return None
    base = root if cleaned.startswith("/") else source.parent
    candidate = (base / cleaned.lstrip("/")).resolve()
    if candidate.exists():
        return candidate
    for suffix in (".md", ".html"):  # wiki-style links carry no extension
        if candidate.with_suffix(suffix).exists():
            return candidate.with_suffix(suffix)
    return candidate


def build_index(root: str | Path, skip_dirs: tuple[str, ...] = (".git", "node_modules", ".lake", "__pycache__")) -> ReferenceIndex:
    base = Path(root).expanduser().resolve()
    index = ReferenceIndex(base)
    for path in base.rglob("*"):
        if path.suffix.lower() not in SCANNABLE or not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ref in _candidates(text):
            target = _resolve(path, ref, base)
            index.outgoing[path].append((ref, target))
            if target is None:
                continue
            if target.exists():
                index.incoming[target].append(path)
            else:
                index.broken.append((path, ref))
    return index


def rewrite_references(index: ReferenceIndex, moves: dict[str | Path, str | Path], *, dry_run: bool = True) -> dict[str, object]:
    """Repoint every referrer after *moves* (old path -> new path) are applied."""
    resolved = {Path(old).resolve(): Path(new).resolve() for old, new in moves.items()}
    edits: list[dict[str, object]] = []
    for source, refs in index.outgoing.items():
        if not source.exists():
            continue
        try:
            text = original = source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        source_dir = (resolved.get(source.resolve(), source)).parent
        for ref, target in refs:
            if target is None or target.resolve() not in resolved:
                continue
            new_ref = Path(os.path.relpath(resolved[target.resolve()], source_dir)).as_posix()
            text = re.sub(rf"(?<=[\"'(\[]){re.escape(ref)}(?=[\"')\]#?])", new_ref, text)
        if text != original:
            edits.append({"file": str(source), "changed": True})
            if not dry_run:
                source.write_text(text, encoding="utf-8")
    return {"dry_run": dry_run, "files_edited": len(edits), "edits": edits}
