"""Universal pre-routing predicates for David-OS.

Every classifier may *propose* a home.  A routing move may execute only after
these deterministic predicates produce a reviewable receipt and a person marks
that receipt reviewed.  These are routing truth predicates: factual questions
about the proposed operation, not claims that a document's contents are true.

The module reads source/destination context and returns data.  It never moves,
renames, deletes, or rewrites a source file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence


SCHEMA = "david-os.routing-predicates.v1"
TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm"}
PROMINENCE_WEIGHTS = {
    "filename": 12,
    "frontmatter_title": 10,
    "h1": 8,
    "heading": 4,
    "body": 1,
}


class PredicateState(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class PredicateResult:
    predicate: str
    state: PredicateState
    reason: str
    evidence: dict


def _decision_signal(value: Mapping[str, object] | None) -> dict | None:
    """Normalize one advisory routing arrow without inventing missing evidence."""
    if not value:
        return None
    destination = str(value.get("destination", "")).strip()
    if not destination:
        return None
    try:
        confidence = max(0.0, min(1.0, float(value.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    evidence = value.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = []
    return {
        "destination": destination,
        "destination_key": _normal(destination),
        "confidence": confidence,
        "evidence": [str(item) for item in evidence[:20]],
    }


def decision_concordance(
    content_signal: Mapping[str, object] | None,
    lineage_signal: Mapping[str, object] | None,
) -> PredicateResult:
    """Compare independent content and lineage arrows."""
    content = _decision_signal(content_signal)
    lineage = _decision_signal(lineage_signal)
    evidence = {"content_signal": content, "lineage_signal": lineage}
    if not content and not lineage:
        return PredicateResult("RP07_DECISION_CONCORDANCE", PredicateState.NOT_APPLICABLE,
                               "content and lineage signals were not supplied", evidence)
    if not content or not lineage:
        return PredicateResult("RP07_DECISION_CONCORDANCE", PredicateState.HOLD,
                               "only one independent routing signal is available", evidence)
    if content["destination_key"] != lineage["destination_key"]:
        return PredicateResult("RP07_DECISION_CONCORDANCE", PredicateState.HOLD,
                               "content and lineage signals point to different destinations", evidence)
    joint_confidence = 1.0 - ((1.0 - content["confidence"]) * (1.0 - lineage["confidence"]))
    evidence["joint_confidence"] = round(joint_confidence, 4)
    if min(content["confidence"], lineage["confidence"]) < 0.5:
        return PredicateResult("RP07_DECISION_CONCORDANCE", PredicateState.HOLD,
                               "signals agree, but at least one is weak", evidence)
    return PredicateResult("RP07_DECISION_CONCORDANCE", PredicateState.PASS,
                           "independent content and lineage signals agree", evidence)


_YAML_TITLE = re.compile(r"(?im)^title\s*:\s*[\"']?(.+?)[\"']?\s*$")
_H1 = re.compile(r"(?m)^#\s+(.+?)\s*$")
_HTML_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_HTML_H1 = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
_TAG = re.compile(r"<[^>]+>")
_LEADING_NUMBER = re.compile(r"^\s*(\d{1,4})(?:[._ -]+)(.+)$")
_NAMED_NUMBER = re.compile(r"(?i)\b(chapter|part|paper|law|book|volume|vol|section|step|phase)[-_ ]*(\d+(?:\.\d+)*)\b")
_CODED_NUMBER = re.compile(r"(?i)^\s*((?:AX[_ -]?)?[A-Z]{0,3}\d+(?:\.\d+)+)\b")
_TRAILING_NUMBER = re.compile(r"(?i)^(.*?)[_ -]+(?:part[_ -]*)?(\d{1,4})$")


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _read(path: Path, limit: int = 100_000) -> str:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def prominent_fields(path: Path) -> list[dict]:
    """Expose the weighted layers; filename/title must outrank body mentions."""
    text = _read(path)
    found = [{"field": "filename", "text": path.stem, "weight": 12}]
    for field, regex, weight in (
        ("frontmatter_title", _YAML_TITLE, 10),
        ("h1", _H1, 8),
        ("frontmatter_title", _HTML_TITLE, 10),
        ("h1", _HTML_H1, 8),
    ):
        match = regex.search(text)
        if match:
            value = " ".join(_TAG.sub(" ", match.group(1)).split())
            if value and not any(row["field"] == field and row["text"] == value for row in found):
                found.append({"field": field, "text": value[:500], "weight": weight})
    if text:
        # The body participates at the deliberately lowest weight. Keep the
        # bounded text for term matching, but do not serialize more than a
        # short evidence excerpt into the eventual receipt.
        found.append({"field": "body", "text": text[:80_000], "weight": 1})
    return found


def prominence_receipt(path: Path, destination_terms: Iterable[str] = ()) -> dict:
    terms = tuple(sorted({_normal(x) for x in destination_terms if _normal(x)}))
    evidence, score = [], 0
    for field in prominent_fields(path):
        words = _normal(field["text"])
        hits = [term for term in terms if term in words]
        field_score = field["weight"] * len(hits)
        score += field_score
        evidence.append({**field, "text": field["text"][:500], "hits": hits, "score": field_score})
    return {"score": score, "terms": list(terms), "layers": evidence, "weights": PROMINENCE_WEIGHTS}


def series_signature(path: Path) -> tuple[str, str] | None:
    stem = path.stem
    match = _CODED_NUMBER.search(stem)
    if match:
        prefix = re.match(r"(?i)(?:AX[_ -]?)?([A-Z]{0,3})", match.group(1)).group(1) or "AXIOM"
        return f"coded:{prefix.upper()}", match.group(1)
    match = _NAMED_NUMBER.search(stem)
    if match:
        return f"named:{match.group(1).lower()}", match.group(2)
    match = _LEADING_NUMBER.match(stem)
    if match:
        return "leading-number", match.group(1)
    match = _TRAILING_NUMBER.match(stem)
    if match and _normal(match.group(1)):
        return f"trailing:{_normal(match.group(1))}", match.group(2)
    return None


def series_neighbours(path: Path) -> list[dict]:
    signature = series_signature(path)
    if not signature or not path.parent.is_dir():
        return []
    kind, _ = signature
    rows = []
    try:
        siblings = path.parent.iterdir()
    except OSError:
        return []
    for sibling in siblings:
        if not sibling.is_file() or sibling == path:
            continue
        other = series_signature(sibling)
        if other and other[0] == kind:
            rows.append({"path": str(sibling.resolve()), "marker": other[1]})
    return sorted(rows, key=lambda row: row["path"].lower())


def folder_sample(folder: Path, limit: int = 50) -> list[str]:
    if not folder.is_dir():
        return []
    try:
        return sorted((p.name for p in folder.iterdir()), key=str.lower)[:limit]
    except OSError:
        return []


def evaluate(
    source: str | Path,
    target: str | Path,
    *,
    destination_terms: Sequence[str] = (),
    batch_targets: Mapping[str, str] | None = None,
    human_approved: bool = False,
    undo_planned: bool = False,
    content_signal: Mapping[str, object] | None = None,
    lineage_signal: Mapping[str, object] | None = None,
) -> dict:
    """Evaluate all universal predicates and return a serializable receipt."""
    source, target = Path(source).resolve(), Path(target).resolve()
    batch = {str(Path(k).resolve()): str(Path(v).resolve()) for k, v in (batch_targets or {}).items()}
    results: list[PredicateResult] = []

    prominence = prominence_receipt(source, destination_terms)
    results.append(PredicateResult(
        "RP01_TITLE_PROMINENCE",
        PredicateState.PASS if prominence["layers"] else PredicateState.HOLD,
        "weighted filename/title evidence recorded" if prominence["layers"] else "no prominent title evidence",
        prominence,
    ))

    neighbours = series_neighbours(source)
    if not neighbours:
        results.append(PredicateResult("RP02_SERIES_INTEGRITY", PredicateState.NOT_APPLICABLE,
                                       "no numbered or named sibling series detected", {}))
    else:
        member_paths = [str(source), *[row["path"] for row in neighbours]]
        missing = [p for p in member_paths if p not in batch]
        homes = {str(Path(batch[p]).parent).lower() for p in member_paths if p in batch}
        if missing:
            state, reason = PredicateState.HOLD, "series members are outside the proposed batch"
        elif len(homes) > 1:
            state, reason = PredicateState.HOLD, "series members would be split across destinations"
        else:
            state, reason = PredicateState.PASS, "complete detected series travels together"
        results.append(PredicateResult("RP02_SERIES_INTEGRITY", state, reason,
                                       {"members": member_paths, "missing": missing, "destination_parents": sorted(homes)}))

    source_sample, target_sample = folder_sample(source.parent), folder_sample(target.parent)
    state = PredicateState.PASS if source_sample else PredicateState.HOLD
    results.append(PredicateResult("RP03_FOLDER_CONTEXT", state,
                                   "source and destination neighbourhood recorded" if source_sample else "source folder could not be inventoried",
                                   {"source_sample": source_sample, "destination_sample": target_sample}))

    target_parents = {str(Path(v).parent).lower() for v in batch.values()}
    results.append(PredicateResult(
        "RP04_DESTINATION_COHERENCE",
        PredicateState.PASS if target not in (source, source.parent) else PredicateState.FAIL,
        "target is distinct from source" if target not in (source, source.parent) else "target does not create a real routing move",
        {"batch_destination_parent_count": len(target_parents)},
    ))
    results.append(PredicateResult("RP05_HUMAN_APPROVAL", PredicateState.PASS if human_approved else PredicateState.HOLD,
                                   "explicit human approval recorded" if human_approved else "human approval not recorded", {}))
    results.append(PredicateResult("RP06_REVERSIBILITY", PredicateState.PASS if undo_planned else PredicateState.HOLD,
                                   "undo/receipt plan recorded" if undo_planned else "undo/receipt plan missing", {}))
    results.append(decision_concordance(content_signal, lineage_signal))

    states = [row.state for row in results]
    verdict = "FAIL" if PredicateState.FAIL in states else "HOLD" if PredicateState.HOLD in states else "PASS"
    return {
        "schema": SCHEMA,
        "source": str(source),
        "target": str(target),
        "verdict": verdict,
        "predicates": [{**asdict(row), "state": row.state.value} for row in results],
    }


def require_passed_receipt(payload: Mapping[str, object], source: Path, target: Path) -> dict:
    receipt = payload.get("routing_predicates")
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise ValueError(f"routing move requires a {SCHEMA} receipt")
    if Path(str(receipt.get("source", ""))).resolve() != source.resolve():
        raise ValueError("routing receipt source does not match move source")
    if Path(str(receipt.get("target", ""))).resolve() != target.resolve():
        raise ValueError("routing receipt target does not match move target")
    if receipt.get("verdict") != "PASS":
        raise ValueError(f"routing predicates have not passed: {receipt.get('verdict')}")
    if not bool(payload.get("routing_predicates_reviewed", False)):
        raise ValueError("routing predicate receipt has not been reviewed")
    return receipt
