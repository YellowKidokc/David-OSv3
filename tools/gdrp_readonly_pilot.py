#!/usr/bin/env python3
"""Read-only GDRP pilot for a same-name, different-content ambiguity.

The target corpus is never modified. The script writes a recovery event,
bounded evidence, the local Ollama response, and a deterministic evaluation to
an explicitly supplied output directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
import urllib.error
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_RECOMMENDATIONS = {"KEEP_STOPPED", "COLLECT_EVIDENCE", "TREAT_AS_DISTINCT_ROLES"}
MAX_EXCERPT = 700
PROMPT_VERSION = "gdrp-master-equation-pilot/v3-notebook"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")[:MAX_EXCERPT]
    text = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text


def choose_family(root: Path, requested: str | None) -> tuple[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".lean", ".json", ".jsonld"}:
            if ".obsidian" not in {part.lower() for part in path.parts}:
                groups[path.name.lower()].append(path)
    names = [requested.lower()] if requested else sorted(groups, key=lambda name: (-len(groups[name]), name))
    for name in names:
        paths = groups.get(name, [])
        if len(paths) > 1 and len({sha256(path) for path in paths}) > 1:
            return name, paths
    raise ValueError("No same-name, different-content family was found")


def evidence_record(root: Path, path: Path, index: int) -> dict[str, Any]:
    stat = path.stat()
    return {
        "evidence_id": f"E{index:02d}",
        "relative_path": str(path.relative_to(root)),
        "sha256": sha256(path),
        "bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "excerpt": bounded_text(path),
    }


def build_packet(root: Path, basename: str, paths: list[Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    event_id = str(uuid.uuid4())
    evidence = [evidence_record(root, path, index) for index, path in enumerate(paths, 1)]
    event = {
        "protocol_version": "gdrp/v1",
        "event_id": event_id,
        "run_id": event_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "program_id": "david-osv3.master-equation-readonly-pilot",
        "program_version": "pilot/v1",
        "operation_id": "select-index-representative",
        "error_code": "AMBIGUOUS_SAME_NAME_DIFFERENT_CONTENT",
        "severity": "warning",
        "message": "The operation cannot infer whether same-name artifacts are revisions, duplicates, or distinct role-specific documents.",
        "output": {
            "content_type": "application/json",
            "data": {"basename": basename, "candidate_count": len(evidence)},
            "truncated": False,
            "redactions": [],
        },
        "metadata": {"read_only": True, "corpus_root": str(root)},
    }
    context = {
        "profile": {
            "purpose": "Conservatively select content for indexing without changing corpus files.",
            "invariants": [
                "Do not rename, move, delete, edit, or declare a filesystem keeper.",
                "A shared basename is not proof that artifacts are duplicates or revisions.",
                "Timestamps and size are not authority evidence.",
                "If lineage or role is unresolved, preserve the stop.",
            ],
            "allowed_actions": ["KEEP_STOPPED", "COLLECT_EVIDENCE", "TREAT_AS_DISTINCT_ROLES"],
        },
        "event": event,
        "evidence": evidence,
    }
    return event, context


def response_schema() -> dict[str, Any]:
    rating = {"type": "number", "minimum": 0, "maximum": 1}
    return {
        "type": "object",
        "required": ["diagnosis", "recommendation", "safe_to_retry", "retry_operation_id", "working_notes", "notes", "corrections"],
        "properties": {
            "diagnosis": {"type": "string"},
            "recommendation": {"enum": sorted(ALLOWED_RECOMMENDATIONS)},
            "safe_to_retry": {"type": "boolean"},
            "retry_operation_id": {"type": ["string", "null"]},
            "working_notes": {"type": "object"},
            "notes": {"type": "array", "items": {"type": "string"}},
            "missing_evidence": {"type": "array", "items": {"type": "string"}},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["correction_id", "action", "note", "expected_result", "ratings"],
                    "properties": {
                        "correction_id": {"type": "string"},
                        "action": {"enum": sorted(ALLOWED_RECOMMENDATIONS)},
                        "note": {"type": "string"},
                        "expected_result": {"type": "string"},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "ratings": {
                            "type": "object",
                            "required": ["diagnosis_confidence", "success_probability", "no_regression_probability", "evidence_coverage", "assumption_load"],
                            "properties": {
                                "diagnosis_confidence": rating,
                                "success_probability": rating,
                                "no_regression_probability": rating,
                                "evidence_coverage": rating,
                                "assumption_load": rating,
                            },
                        },
                    },
                },
            },
        },
    }


def ask_ollama(context: dict[str, Any], model: str, url: str, timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    request_body = {
        "model": model,
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 900},
        "prompt": diagnostic_prompt(context),
    }
    req = urllib.request.Request(
        url, data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    content = raw.get("response", "") or raw.get("message", {}).get("content", "")
    return json.loads(content), raw


def diagnostic_prompt(context: dict[str, Any]) -> str:
    return (
        "You are an AI diagnostic collaborator receiving a request from another AI/program on David's behalf. "
        "David wants candid help: say when you do not know, disagree when evidence warrants it, and request another "
        "tool, program, file, check, or human answer when that would improve the result. Take time to organize the "
        "problem and leave useful notes so the next attempt does not start from zero. Do not expose private hidden "
        "reasoning; provide concise inspectable working notes. "
        "You are the advisory diagnostician in a read-only recovery protocol. "
        "Analyze only the supplied evidence. Same basename does not establish duplicate or revision lineage. "
        "Do not select a filesystem keeper and do not propose mutation. Determine whether the files appear to "
        "serve distinct roles, or state what read-only evidence is still required. safe_to_retry may be true only "
        "if the ambiguity has been resolved without inventing lineage. A classification-only conclusion does not by itself "
        "authorize retrying select-index-representative. Give notes and calibrated ratings for every correction.\n\n"
        "Return one JSON object with: diagnosis (string), recommendation, safe_to_retry (boolean), "
        "retry_operation_id (the exact operation safe to retry, or null), working_notes (object), notes "
        "(array), missing_evidence (array), evidence_ids (array), and corrections (non-empty array). Each "
        "correction requires correction_id, action, note, expected_result, evidence_ids, and ratings containing "
        "diagnosis_confidence, success_probability, no_regression_probability, evidence_coverage, and "
        "assumption_load as numbers from 0 to 1. Allowed actions/recommendations: KEEP_STOPPED, "
        "COLLECT_EVIDENCE, TREAT_AS_DISTINCT_ROLES.\n\n"
        "working_notes must contain situation, known, unknown, assumptions, needs, helpful_tools, safest_next_step, "
        "cautions, and note_to_operator. known/unknown/assumptions/needs/helpful_tools/cautions are arrays of strings.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def ask_deepseek_api(context: dict[str, Any], model: str, url: str, timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON. Preserve uncertainty and never propose mutation."},
            {"role": "user", "content": diagnostic_prompt(context)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 2400,
        "stream": False,
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc
    content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
    return json.loads(content), raw


def evaluate(answer: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    evidence_ids = {item["evidence_id"] for item in context["evidence"]}
    failures: list[str] = []
    recommendation = answer.get("recommendation")
    if recommendation not in ALLOWED_RECOMMENDATIONS:
        failures.append("recommendation is not allowlisted")
    if answer.get("safe_to_retry") is True and recommendation != "TREAT_AS_DISTINCT_ROLES":
        failures.append("safe_to_retry conflicts with unresolved recommendation")
    retry_operation = answer.get("retry_operation_id")
    original_operation = context["event"]["operation_id"]
    if answer.get("safe_to_retry") is True and retry_operation != original_operation:
        failures.append("safe_to_retry does not name the exact stopped operation")
    if answer.get("safe_to_retry") is False and retry_operation not in (None, ""):
        failures.append("retry_operation_id must be null when safe_to_retry is false")
    advisory_text = " ".join([
        str(answer.get("diagnosis", "")),
        *[str(item) for item in answer.get("notes") or []],
        *[str(item.get("expected_result", "")) for item in answer.get("corrections") or [] if isinstance(item, dict)],
    ])
    if answer.get("safe_to_retry") is True and re.search(r"\b(does not authorize|out of scope|or defers?|must defer|remains? stopped)\b", advisory_text, re.I):
        failures.append("safe_to_retry contradicts the diagnosis or expected result")
    cited = set(answer.get("evidence_ids") or [])
    if not cited or not cited.issubset(evidence_ids):
        failures.append("diagnosis has missing or invalid evidence references")
    corrections = answer.get("corrections")
    working = answer.get("working_notes")
    required_note_fields = {
        "situation", "known", "unknown", "assumptions", "needs", "helpful_tools",
        "safest_next_step", "cautions", "note_to_operator",
    }
    if not isinstance(working, dict) or not required_note_fields.issubset(working):
        failures.append("inspectable working notes are incomplete")
    if not isinstance(corrections, list) or not corrections:
        failures.append("no rated correction was returned")
    else:
        for correction in corrections:
            if correction.get("action") not in ALLOWED_RECOMMENDATIONS:
                failures.append(f"{correction.get('correction_id')}: action is not allowlisted")
            if not correction.get("note"):
                failures.append(f"{correction.get('correction_id')}: correction note is missing")
            ratings = correction.get("ratings") or {}
            for field in ("diagnosis_confidence", "success_probability", "no_regression_probability", "evidence_coverage", "assumption_load"):
                value = ratings.get(field)
                if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    failures.append(f"{correction.get('correction_id')}: invalid {field}")
    mutation_words = re.compile(r"\b(rename|move|delete|overwrite|keeper)\b", re.I)
    for correction in corrections or []:
        if mutation_words.search(str(correction.get("action", ""))):
            failures.append(f"{correction.get('correction_id')}: mutation action proposed")
    return {
        "schema_and_policy_pass": not failures,
        "failures": failures,
        "corpus_modified": False,
        "resolution_claim": recommendation,
        "retry_allowed_by_evaluator": not failures and answer.get("safe_to_retry") is True,
        "interpretation": (
            "DeepSeek recognized role-specific artifacts; indexing may treat them as distinct, but no filesystem keeper was chosen."
            if not failures and recommendation == "TREAT_AS_DISTINCT_ROLES"
            else "The ambiguity remains stopped pending additional evidence or a valid assessment."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--basename")
    parser.add_argument("--model", default="deepseek-r1:latest")
    parser.add_argument("--provider", choices=("ollama", "deepseek-api"), default="ollama")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--deepseek-url", default="https://api.deepseek.com/chat/completions")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-candidates", type=int, default=4)
    args = parser.parse_args()

    root = args.root.resolve(strict=True)
    basename, paths = choose_family(root, args.basename)
    paths = paths[:max(2, args.max_candidates)]
    event, context = build_packet(root, basename, paths)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "recovery-event.json").write_text(json.dumps(event, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / "diagnostic-context.json").write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        if args.provider == "deepseek-api":
            answer, raw = ask_deepseek_api(context, args.model, args.deepseek_url, args.timeout)
        else:
            answer, raw = ask_ollama(context, args.model, args.ollama_url, args.timeout)
        evaluation = evaluate(answer, context)
        status = "PASS" if evaluation["schema_and_policy_pass"] else "HOLD"
    except Exception as exc:
        answer, raw = {}, {"error": str(exc)}
        evaluation = {
            "schema_and_policy_pass": False, "failures": [str(exc)],
            "corpus_modified": False, "retry_allowed_by_evaluator": False,
            "interpretation": "Model failure preserved the stop.",
        }
        status = "MODEL_FAILURE"
    (args.out / "deepseek-assessment.json").write_text(json.dumps(answer, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out / "adviser-receipt.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    attempt_id = str(uuid.uuid4())
    working = answer.get("working_notes") if isinstance(answer, dict) else None
    if not isinstance(working, dict):
        working = {
            "situation": "The adviser did not return usable working notes.",
            "known": [f"Adviser attempt ended with: {raw.get('error', 'invalid response')}"],
            "unknown": ["No adviser diagnosis was accepted."],
            "assumptions": [], "needs": ["A healthy adviser response"],
            "helpful_tools": ["Adviser health check"],
            "safest_next_step": "Keep the host operation stopped.",
            "cautions": ["Do not interpret adviser failure as permission to retry the host."],
            "note_to_operator": "The diagnostic adviser failed; no source operation was authorized.",
        }
    note = {
        "note_version": "gdrp-adviser-note/v1",
        "incident_id": event["event_id"], "attempt_id": attempt_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adviser": {"provider": args.provider, "model": args.model, "prompt_version": PROMPT_VERSION},
        **working, "evidence_ids": answer.get("evidence_ids", []) if isinstance(answer, dict) else [],
    }
    with (args.out / "adviser-notes.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(note, ensure_ascii=False) + "\n")
    (args.out / "evaluation.json").write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {
        "status": status, "provider": args.provider, "model": args.model, "root": str(root), "basename": basename,
        "candidate_count": len(paths), "output": str(args.out), "evaluation": evaluation,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
