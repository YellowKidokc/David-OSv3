"""Writing-quality snapshot for any text or markup file.

Structural, not stylistic: length, sentence and paragraph shape, heading order,
link and code density, leftover drafting marks. Scores 0-100 with the reasons
attached, so a folder can be sorted by "how finished does this read" without a
model in the loop. Snapshots are comparable across runs — take one now, take
another after edits, diff the two.
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

READABLE = {".md", ".markdown", ".txt", ".html", ".htm", ".rst"}

_TAG = re.compile(r"(?s)<(script|style)\b.*?</\1>|<[^>]+>")
_FRONT = re.compile(r"(?s)\A---.*?\n---\s*")
_CODE = re.compile(r"(?s)```.*?```|~~~.*?~~~")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
_LINK = re.compile(r"\[[^\]]*\]\([^)]*\)|href\s*=", re.I)
_SENTENCE = re.compile(r"[.!?]+[\s\"')\]]|\n{2,}")
_TODO = re.compile(r"\b(TODO|TBD|FIXME|XXX|PLACEHOLDER|LOREM IPSUM|\[\s*\]|WIP)\b", re.I)


@dataclass
class QualityScore:
    path: str
    score: int
    grade: str
    words: int
    paragraphs: int
    headings: int
    links: int
    mean_sentence_words: float
    todos: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _grade(score: int) -> str:
    for cutoff, letter in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if score >= cutoff:
            return letter
    return "F"


def score_text(text: str, path: str = "") -> QualityScore:
    body = _CODE.sub(" ", _TAG.sub(" ", _FRONT.sub("", text)))
    words = body.split()
    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    headings = _HEADING.findall(text)
    sentences = [s for s in _SENTENCE.split(body) if s.strip()]
    lengths = [len(s.split()) for s in sentences if s.split()]
    mean_len = round(statistics.mean(lengths), 1) if lengths else 0.0
    links = len(_LINK.findall(text))
    todos = len(_TODO.findall(text))

    score, reasons = 100, []

    def penalise(points: int, reason: str) -> None:
        nonlocal score
        score -= points
        reasons.append(reason)

    if len(words) < 25:
        penalise(55, f"near-empty: {len(words)} words")
    elif len(words) < 150:
        penalise(25, f"very short: {len(words)} words")
    elif len(words) < 400:
        penalise(10, f"short: {len(words)} words")

    if not headings and len(words) > 400:
        penalise(12, "long text with no headings")
    elif headings:
        levels = [len(h[0]) for h in headings]
        if levels and levels[0] > 1:
            penalise(5, "does not start at a top-level heading")
        if any(b - a > 1 for a, b in zip(levels, levels[1:])):
            penalise(5, "heading levels skip a level")

    if mean_len > 35:
        penalise(12, f"long sentences (mean {mean_len} words)")
    elif mean_len > 27:
        penalise(6, f"longish sentences (mean {mean_len} words)")

    if paragraphs:
        longest = max(len(p.split()) for p in paragraphs)
        if longest > 220:
            penalise(8, f"one paragraph runs {longest} words")

    if todos:
        penalise(min(20, 5 * todos), f"{todos} unfinished marker(s)")

    if len(words) > 200 and links == 0:
        penalise(4, "no links or references")

    score = max(0, min(100, score))
    return QualityScore(path=path, score=score, grade=_grade(score), words=len(words),
                        paragraphs=len(paragraphs), headings=len(headings), links=links,
                        mean_sentence_words=mean_len, todos=todos, reasons=reasons)


def score_file(path: str | Path) -> QualityScore | None:
    file = Path(path)
    if file.suffix.lower() not in READABLE or not file.is_file():
        return None
    try:
        return score_text(file.read_text(encoding="utf-8", errors="ignore"), str(file))
    except OSError:
        return None


def snapshot(root: str | Path, skip_dirs: tuple[str, ...] = (".git", "node_modules", ".lake", "__pycache__")) -> dict[str, object]:
    base = Path(root).expanduser().resolve()
    scores = [s for p in base.rglob("*")
              if p.suffix.lower() in READABLE and not any(part in skip_dirs for part in p.parts)
              for s in [score_file(p)] if s]
    values = [s.score for s in scores]
    buckets: dict[str, int] = {}
    for s in scores:
        buckets[s.grade] = buckets.get(s.grade, 0) + 1
    return {
        "root": str(base),
        "taken": datetime.now().isoformat(timespec="seconds"),
        "files": len(scores),
        "mean_score": round(statistics.mean(values), 1) if values else 0.0,
        "median_score": round(statistics.median(values), 1) if values else 0.0,
        "grades": dict(sorted(buckets.items())),
        "worst": [s.to_dict() for s in sorted(scores, key=lambda s: s.score)[:50]],
        "scores": [s.to_dict() for s in scores],
    }


def save_snapshot(root: str | Path, out_dir: str | Path) -> Path:
    data = snapshot(root)
    out = Path(out_dir) / f"quality_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def compare(before: dict[str, object] | str | Path, after: dict[str, object] | str | Path) -> dict[str, object]:
    """Diff two snapshots: which files improved, which slipped, which are new."""
    def load(value):
        return value if isinstance(value, dict) else json.loads(Path(value).read_text(encoding="utf-8"))

    old, new = load(before), load(after)
    old_scores = {s["path"]: s["score"] for s in old.get("scores", [])}
    new_scores = {s["path"]: s["score"] for s in new.get("scores", [])}
    moved = [{"path": p, "from": old_scores[p], "to": new_scores[p], "delta": new_scores[p] - old_scores[p]}
             for p in set(old_scores) & set(new_scores) if new_scores[p] != old_scores[p]]
    return {
        "mean_before": old.get("mean_score"), "mean_after": new.get("mean_score"),
        "improved": sorted([m for m in moved if m["delta"] > 0], key=lambda m: -m["delta"]),
        "worsened": sorted([m for m in moved if m["delta"] < 0], key=lambda m: m["delta"]),
        "added": sorted(set(new_scores) - set(old_scores)),
        "removed": sorted(set(old_scores) - set(new_scores)),
    }
