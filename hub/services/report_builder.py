"""Compact FIS report generation and structured report Q&A.

The builder accepts loosely-shaped FIS scan dictionaries so routes/workers can
feed it exact duplicate groups, near-duplicate pairs, routing suggestions,
rename proposals, classifications, and file inventories without coupling this
service to a single scanner output schema. It never executes file actions; it
only creates reviewable suggestions and records preference feedback.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
import uuid
from pathlib import Path
from typing import Any, Iterable

REPORT_LIMITS = {
    "anomalies": 8,
    "suggestions": 12,
    "stats_domains": 8,
    "stats_extensions": 8,
}

_REPORT_CACHE: dict[str, dict[str, Any]] = {}


@dataclass
class ReportBuilder:
    """Build short, action-oriented FIS reports from scan outputs."""

    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def build(
        self,
        scan: dict[str, Any],
        *,
        source: str | None = None,
        duration: str | float | int | None = None,
        report_id: str | None = None,
    ) -> dict[str, Any]:
        report_id = report_id or f"fis-{uuid.uuid4().hex[:12]}"
        files = list(_iter_files(scan))
        exact_groups = _exact_duplicate_groups(scan)
        near_dups = _near_duplicate_pairs(scan)
        routes = _routing_suggestions(scan)
        renames = _rename_suggestions(scan)
        classifications = _classification_rows(scan, files)

        anomalies = _build_anomalies(exact_groups, near_dups, routes, classifications)
        suggestions = _build_suggestions(routes, renames, near_dups)
        stats = _build_stats(files, exact_groups, classifications)
        text = _render_text(
            timestamp=self.now.isoformat(timespec="seconds"),
            source=source or scan.get("source") or scan.get("folder") or scan.get("source_folder") or "unknown",
            duration=_format_duration(duration or scan.get("duration") or scan.get("duration_seconds")),
            anomalies=anomalies,
            suggestions=suggestions,
            stats=stats,
        )
        report = {
            "report_id": report_id,
            "timestamp": self.now.isoformat(timespec="seconds"),
            "source": source or scan.get("source") or scan.get("folder") or scan.get("source_folder"),
            "duration": _format_duration(duration or scan.get("duration") or scan.get("duration_seconds")),
            "sections": {
                "anomalies": anomalies,
                "suggestions": suggestions,
                "statistics": stats,
                "actions_taken": [],
            },
            "text": text,
        }
        _REPORT_CACHE[report_id] = report
        return report


def build_report(scan: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper used by routes and workers."""

    return ReportBuilder().build(scan, **kwargs)


def get_report(report_id: str) -> dict[str, Any] | None:
    return _REPORT_CACHE.get(report_id)


def record_feedback(report_id: str, suggestion_id: str, rating: int, accepted: bool | None = None) -> dict[str, Any]:
    """Record user preference feedback for a report suggestion.

    Ratings map to preference learning as requested: 4-5 positive, 1-2 negative,
    3 neutral. Neutral feedback is stored on the report but not used to train the
    binary preference ensemble.
    """

    report = get_report(report_id)
    if not report:
        raise KeyError(report_id)
    rating = max(1, min(5, int(rating)))
    suggestions = report["sections"].get("suggestions", [])
    suggestion = next((s for s in suggestions if s.get("id") == suggestion_id), None)
    if not suggestion:
        raise KeyError(suggestion_id)
    accepted = rating >= 4 if accepted is None else bool(accepted)
    feedback = {"suggestion_id": suggestion_id, "rating": rating, "accepted": accepted, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    report.setdefault("feedback", []).append(feedback)
    if rating != 3:
        _learn_preference(suggestion, accepted=accepted, rating=rating)
    return {"status": "recorded", "feedback": feedback, "preference_trained": rating != 3}


def answer_report_question(report: dict[str, Any], question: str) -> dict[str, str]:
    """Structured local Q&A over report JSON; no external LLM calls."""

    q = (question or "").lower()
    sections = report.get("sections", {})
    anomalies = sections.get("anomalies", [])
    suggestions = sections.get("suggestions", [])
    stats = sections.get("statistics", {})
    if any(term in q for term in ("summar", "overview", "what happened")):
        answer = summarize_report(report)
    elif "duplicate" in q or "dups" in q:
        exact = stats.get("exact_duplicate_groups", 0)
        affected = stats.get("duplicate_files", 0)
        coverage = stats.get("duplicate_coverage_pct", 0)
        answer = f"{exact} exact duplicate groups found, affecting {affected} files ({coverage}% duplicate coverage)."
    elif "near" in q or "similar" in q:
        near = [a for a in anomalies if a.get("kind") == "near_duplicate"]
        answer = f"{len(near)} high-confidence near-duplicate pairs are highlighted in the report."
    elif "orphan" in q or "no routing" in q:
        orphans = [a for a in anomalies if a.get("kind") == "orphan"]
        answer = f"{len(orphans)} files have no routing match in the anomaly list."
    elif "next" in q or "action" in q:
        top = suggestions[:3]
        if not top:
            answer = "No suggested next actions are currently queued."
        else:
            answer = "Next actions: " + "; ".join(s.get("question", s.get("summary", "review suggestion")) for s in top)
    else:
        answer = summarize_report(report)
    return {"answer": answer}


def summarize_report(report: dict[str, Any]) -> str:
    sections = report.get("sections", {})
    stats = sections.get("statistics", {})
    anomalies = sections.get("anomalies", [])
    suggestions = sections.get("suggestions", [])
    return (
        f"FIS scanned {stats.get('total_files', 0)} files from {report.get('source') or 'the selected source'} "
        f"and found {len(anomalies)} attention items. "
        f"There are {stats.get('exact_duplicate_groups', 0)} exact duplicate groups, "
        f"{stats.get('duplicate_coverage_pct', 0)}% duplicate coverage, and {len(suggestions)} reviewable suggestions."
    )


def _iter_files(scan: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("files", "items", "records", "file_records"):
        value = scan.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item
            return


def _exact_duplicate_groups(scan: dict[str, Any]) -> list[dict[str, Any]]:
    groups = scan.get("exact_duplicates") or scan.get("duplicate_groups") or scan.get("duplicates") or []
    normalized = []
    for group in groups:
        files = group.get("files") if isinstance(group, dict) else group
        if isinstance(files, list) and len(files) >= 2:
            normalized.append({"files": files, "count": len(files), **(group if isinstance(group, dict) else {})})
    return normalized


def _near_duplicate_pairs(scan: dict[str, Any]) -> list[dict[str, Any]]:
    pairs = scan.get("near_duplicates") or scan.get("near_dups") or scan.get("similar_files") or []
    out = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        score = pair.get("jaccard", pair.get("score", pair.get("similarity", 0))) or 0
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        if score >= 0.9:
            out.append({**pair, "jaccard": round(score, 4)})
    return sorted(out, key=lambda p: p.get("jaccard", 0), reverse=True)


def _routing_suggestions(scan: dict[str, Any]) -> list[dict[str, Any]]:
    routes = scan.get("routing_suggestions") or scan.get("routes") or scan.get("intake_results") or []
    out = []
    for item in routes:
        if not isinstance(item, dict):
            continue
        target = item.get("target_folder") or item.get("target") or item.get("route")
        path = item.get("path") or item.get("file") or item.get("source")
        if target or path:
            out.append({**item, "target_folder": target, "path": path})
    return out


def _rename_suggestions(scan: dict[str, Any]) -> list[dict[str, Any]]:
    renames = scan.get("rename_proposals") or scan.get("renames") or scan.get("proposed_names") or []
    out = []
    for item in renames:
        if not isinstance(item, dict):
            continue
        current = item.get("current_name") or item.get("name") or Path(str(item.get("path", ""))).name
        proposed = item.get("proposed_name") or item.get("new_name")
        if current and proposed:
            out.append({**item, "current_name": current, "proposed_name": proposed, "spelling_correction": _is_spelling_correction(current, proposed, item)})
    return out


def _classification_rows(scan: dict[str, Any], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = scan.get("classifications") or files or []
    return [r for r in rows if isinstance(r, dict)]


def _build_anomalies(exact_groups, near_dups, routes, classifications) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for group in sorted(exact_groups, key=lambda g: g.get("count", len(g.get("files", []))), reverse=True):
        count = group.get("count", len(group.get("files", [])))
        if count >= 5:
            anomalies.append({"kind": "exact_duplicate", "severity": "high", "summary": f"File exists in {count} locations", "files": group.get("files", [])[:8]})
    for pair in near_dups[: REPORT_LIMITS["anomalies"]]:
        left = pair.get("left") or pair.get("a") or pair.get("file_a") or pair.get("path")
        right = pair.get("right") or pair.get("b") or pair.get("file_b") or pair.get("match")
        anomalies.append({"kind": "near_duplicate", "severity": "medium", "summary": f"Near-duplicate article pair ({pair.get('jaccard', 0):.2f} Jaccard)", "files": [left, right]})
    for route in routes:
        if not route.get("target_folder"):
            anomalies.append({"kind": "orphan", "severity": "medium", "summary": "No routing match", "file": route.get("path")})
    for row in classifications:
        domains = row.get("domains") or row.get("domain_scores") or {}
        if isinstance(domains, dict):
            top = sorted(domains.items(), key=lambda kv: kv[1], reverse=True)[:2]
            if len(top) == 2 and abs(float(top[0][1]) - float(top[1][1])) <= 0.05:
                anomalies.append({"kind": "conflicting_domain", "severity": "medium", "summary": f"Conflicting domains: {top[0][0]} vs {top[1][0]}", "file": row.get("path") or row.get("name")})
    return anomalies[: REPORT_LIMITS["anomalies"]]


def _build_suggestions(routes, renames, near_dups) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    spelling = [r for r in renames if r.get("spelling_correction")]
    structural = [r for r in renames if not r.get("spelling_correction")]
    for item in spelling + structural:
        current, proposed = item["current_name"], item["proposed_name"]
        kind = "spelling_correction" if item.get("spelling_correction") else "rename"
        suggestions.append({
            "id": f"sug-{len(suggestions)+1}",
            "kind": kind,
            "badge": "RED" if kind == "spelling_correction" else None,
            "summary": f"Rename {current} → {proposed}",
            "question": f"Rename \"{current}\" → \"{proposed}\"?",
            "feedback": {"accept": True, "reject": True, "rate_1_to_5": True},
            "proposal": {"current_name": current, "proposed_name": proposed, "tags": item.get("tags", [])},
        })
    route_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for route in routes:
        if route.get("target_folder"):
            route_groups[str(route["target_folder"])].append(route)
    for target, items in sorted(route_groups.items()):
        for route in items[:3]:
            path = route.get("path") or "file"
            suggestions.append({
                "id": f"sug-{len(suggestions)+1}",
                "kind": "route",
                "summary": f"Route {Path(str(path)).name} → {target}",
                "question": f"Route \"{path}\" → {target}/?",
                "feedback": {"accept": True, "reject": True, "rate_1_to_5": True},
                "proposal": {"path": path, "target_folder": target},
            })
    if near_dups:
        suggestions.append({
            "id": f"sug-{len(suggestions)+1}",
            "kind": "family_consolidation",
            "summary": f"Review {len(near_dups)} article-family near-duplicate pairs for consolidation",
            "question": "Group these reading-level/article variants into families?",
            "feedback": {"accept": True, "reject": True, "rate_1_to_5": True},
            "proposal": {"near_duplicate_count": len(near_dups)},
        })
    return suggestions[: REPORT_LIMITS["suggestions"]]


def _build_stats(files, exact_groups, classifications) -> dict[str, Any]:
    ext = Counter((Path(str(f.get("path") or f.get("name") or "")).suffix.lower() or "[none]") for f in files)
    domains = Counter((f.get("domain") or f.get("primary_domain") or "unknown") for f in classifications)
    levels = Counter((f.get("reading_level") or f.get("level") or "unknown") for f in classifications)
    duplicate_files = len({str(path) for group in exact_groups for path in group.get("files", [])})
    total = max(len(files), duplicate_files)
    return {
        "total_files": total,
        "files_by_domain": dict(domains.most_common(REPORT_LIMITS["stats_domains"])),
        "files_by_reading_level": dict(levels.most_common()),
        "files_by_extension": dict(ext.most_common(REPORT_LIMITS["stats_extensions"])),
        "exact_duplicate_groups": len(exact_groups),
        "duplicate_files": duplicate_files,
        "duplicate_coverage_pct": round((duplicate_files / total) * 100, 1) if total else 0,
    }


def _render_text(timestamp, source, duration, anomalies, suggestions, stats) -> str:
    lines = [f"REPORT: FIS Scan — {timestamp}", f"Source: {source}", f"Duration: {duration}", "", "== ANOMALIES =="]
    lines += [f"- {a.get('summary')}" for a in anomalies] or ["- None found."]
    lines += ["", "== SUGGESTIONS =="]
    lines += [f"- {s.get('question', s.get('summary'))}" for s in suggestions] or ["- No suggestions queued."]
    lines += ["", "== STATISTICS ==", f"- Total files scanned: {stats['total_files']}", f"- Exact duplicate groups: {stats['exact_duplicate_groups']} ({stats['duplicate_coverage_pct']}% coverage)", f"- Files by domain: {json.dumps(stats['files_by_domain'])}", f"- Files by reading level: {json.dumps(stats['files_by_reading_level'])}", f"- Files by extension: {json.dumps(stats['files_by_extension'])}", "", "== ACTIONS TAKEN ==", "- None. Awaiting explicit approval."]
    return "\n".join(lines)


def _format_duration(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, (int, float)):
        return f"{value:.1f}s"
    return str(value)


def _is_spelling_correction(current: str, proposed: str, item: dict[str, Any]) -> bool:
    if item.get("spelling_correction") or item.get("rename_type") == "spelling":
        return True
    c_stem = Path(current).stem.lower()
    p_stem = Path(proposed).stem.lower()
    c_norm = re.sub(r"[^a-z0-9]", "", c_stem)
    p_norm = re.sub(r"[^a-z0-9]", "", p_stem)
    if not c_norm or not p_norm:
        return False
    # Spelling fixes tend to preserve almost all characters and extension.
    length_gap = abs(len(c_norm) - len(p_norm)) / max(len(c_norm), len(p_norm))
    common = sum(1 for a, b in zip(c_norm, p_norm) if a == b) / max(len(c_norm), len(p_norm))
    return Path(current).suffix == Path(proposed).suffix and length_gap <= 0.15 and common >= 0.72


def _learn_preference(suggestion: dict[str, Any], *, accepted: bool, rating: int) -> None:
    try:
        import sys
        engine_path = Path(__file__).resolve().parents[3] / "engine"
        if str(engine_path) not in sys.path:
            sys.path.insert(0, str(engine_path))
        from preference_engine import get_engine  # type: ignore

        proposal = dict(suggestion.get("proposal") or {})
        proposal.update({"suggestion_kind": suggestion.get("kind"), "rating": rating})
        get_engine().learn(proposal, accepted, note=f"fis_report_rating={rating}")
    except Exception:
        # Feedback remains attached to the report even when optional engines are unavailable.
        return
