"""Unified v3 sidecar: standing score, lossless trigger, read older formats.

Older pieces this folds in (read, never delete):
  .canon.sidecar.json  tools/sidecar_creator.py
  .chi                 filetagger / classification sidecar
  .fmeta               identity sidecar
  .fisnote             folder/file research note
  D:\\_FIS_STATE\\keyword_registry.json  (optional lexicon, not required at scan time)

Nothing here renames or moves a source file. High standing only queues a
proposal for the approval GUI.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "fis_config.json"
STATE_REGISTRY = Path(r"D:\_FIS_STATE\keyword_registry.json")

SIDECAR_SUFFIXES = (
    ".canon.sidecar.json",
    ".chi",
    ".fmeta",
    ".fmeta.chi",
    ".fisnote",
    ".fistag",
    ".fisdead",
)

_DEFAULTS = {
    "canon_standing_threshold": 0.75,
    "doc_type_confidence_min": 0.60,
    "chi_sum_min": 1,
    "write_canon_sidecar_on_trigger": True,
}


def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    try:
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sibling_paths(source: Path) -> dict[str, Path]:
    return {suffix: Path(str(source) + suffix) for suffix in SIDECAR_SUFFIXES}


def _load_json_or_notes(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    text = text.strip()
    if not text:
        return {}
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"raw": data}
        except json.JSONDecodeError:
            pass
    out: dict[str, Any] = {"sidecar_type": path.suffix.lstrip("."), "notes": text[:4000]}
    for line in text.splitlines()[:40]:
        if ":" in line and not line.startswith("#"):
            key, _, value = line.partition(":")
            key = key.strip()
            if key and len(key) < 40:
                out[key] = value.strip()
    return out


def read_existing(source: Path) -> dict[str, Any]:
    """Merge every sibling sidecar into one dict. Existing human fields win."""
    merged: dict[str, Any] = {}
    for suffix, path in sibling_paths(source).items():
        piece = _load_json_or_notes(path)
        if not piece:
            continue
        piece["_path"] = str(path)
        merged[suffix] = piece
        if suffix == ".canon.sidecar.json":
            merged["canon"] = piece
        if suffix == ".chi":
            merged["chi_sidecar"] = piece
    return merged


def classify_canon_standing(source: Path, classification: dict, proposal: dict | None = None) -> dict:
    """Cheap standing score from classification + existing sidecars. No extra content read."""
    existing = read_existing(source)
    canon = existing.get("canon") or {}
    chi = classification.get("chi") or {}
    if classification.get("chi_sum") is not None:
        chi_sum = float(classification.get("chi_sum") or 0)
    elif isinstance(chi, dict):
        chi_sum = float(sum(float(v or 0) for v in chi.values()))
    else:
        chi_sum = 0.0
    confidence = float(classification.get("confidence") or 0)
    type_conf = float(classification.get("type_confidence") or 0)
    doc_type = str(classification.get("doc_type") or "UNSCANNED")
    flags: list[str] = []

    if canon.get("contradictions"):
        flags.append("CONTRADICTS")
    seals = canon.get("seals") or []
    if any(str(s.get("state") or "").upper() in {"SEAL_STALE", "STALE"} for s in seals if isinstance(s, dict)):
        flags.append("SEAL_STALE")
    if any(str(s.get("state") or "").upper() in {"SEAL_AHEAD", "AHEAD"} for s in seals if isinstance(s, dict)):
        flags.append("SEAL_AHEAD")
    if any(str(s.get("state") or "").upper() in {"SEAL_TAMPERED", "TAMPERED"} for s in seals if isinstance(s, dict)):
        flags.append("SEAL_TAMPERED")
    if any(str(s.get("state") or "").upper() in {"SEAL_BROKEN", "BROKEN"} for s in seals if isinstance(s, dict)):
        flags.append("SEAL_BROKEN")
    seals_current = bool(seals) and not any(
        f in flags for f in ("SEAL_STALE", "SEAL_AHEAD", "SEAL_TAMPERED", "SEAL_BROKEN")
    )
    status = str(canon.get("status") or "").lower()
    if status in {"canonical", "reference"} and confidence < 0.45:
        flags.append("DRIFTED")
    name = source.name.lower()
    if status in {"canonical", "reference"} and any(token in name for token in (" copy", "_old", "-old", "final_final", "untitled")):
        flags.append("OUTDATED")
    if not classification.get("chi_factor"):
        flags.append("MISSING_FIELDS")
    if doc_type in {"UNSCANNED", "UNTYPED", "UNREADABLE"}:
        flags.append("UNTYPED")

    score = round(
        0.40 * min(1.0, confidence)
        + 0.25 * min(1.0, type_conf)
        + 0.20 * min(1.0, chi_sum / 8.0)
        + 0.15 * (1.0 if status in {"canonical", "candidate", "reference"} else 0.4),
        3,
    )
    if seals_current:
        score = min(1.0, round(score + 0.12, 3))
    if "CONTRADICTS" in flags:
        score = min(score, 0.49)
    if "DRIFTED" in flags:
        score = min(score, 0.55)

    cfg = load_config()
    trips = (
        score >= float(cfg["canon_standing_threshold"])
        and type_conf >= float(cfg["doc_type_confidence_min"])
        and chi_sum >= float(cfg["chi_sum_min"])
        and doc_type not in {"UNSCANNED", "UNTYPED", "UNREADABLE"}
        and "CONTRADICTS" not in flags
    )
    proposed = (proposal or {}).get("proposed_name") or ""
    name_changed = bool(proposed) and proposed.lower() != source.name.lower()
    lossless_trigger = trips and name_changed and (proposal or {}).get("decision") != "skip"

    if "CONTRADICTS" in flags:
        standing = "CONTRADICTS"
    elif "DRIFTED" in flags:
        standing = "DRIFTED"
    elif "OUTDATED" in flags:
        standing = "OUTDATED"
    elif lossless_trigger or score >= float(cfg["canon_standing_threshold"]):
        standing = "CANDIDATE" if not status == "canonical" else "OK"
        if trips and not flags:
            standing = "OK"
    elif score >= 0.50:
        standing = "CANDIDATE"
    else:
        standing = "WATCH"

    return {
        "canon_standing": standing,
        "canon_score": score,
        "drift_flags": flags,
        "promotion_candidate": standing in {"CANDIDATE", "OK"} and trips,
        "lossless_trigger": lossless_trigger,
        "existing": {k: True for k in existing if k.startswith(".")},
        "sidecar_status": status or "unknown",
        "chi_sum": chi_sum,
        "config": {
            "canon_standing_threshold": cfg["canon_standing_threshold"],
            "doc_type_confidence_min": cfg["doc_type_confidence_min"],
        },
    }


def build_canon_sidecar(source: Path, classification: dict, standing: dict, identity: dict) -> dict:
    existing = (read_existing(source).get("canon") or {})
    payload = {
        "sidecar_type": "canon_status",
        "version": "3.0",
        "created_at": existing.get("created_at") or utc_now(),
        "updated_at": utc_now(),
        "created_by": "David-OS v3 FIS scanner",
        "status": existing.get("status") or ("candidate" if standing["promotion_candidate"] else "working"),
        "classification": classification.get("doc_type") or existing.get("classification") or "unclassified",
        "notes": existing.get("notes") or "",
        "lineage": existing.get("lineage") or {"source": identity, "parent_sidecars": [], "rulings": []},
        "filename_grammar": identity.get("filename_grammar", "unclassified"),
        "domain_code": identity.get("domain_code"),
        "type_code": identity.get("type_code"),
        "claim_ids": existing.get("claim_ids") or [],
        "evidence_tier": existing.get("evidence_tier") or "unknown",
        "rulings": existing.get("rulings") or (existing.get("lineage") or {}).get("rulings") or [],
        "contradictions": existing.get("contradictions") or [],
        "wanted": existing.get("wanted") or [],
        "written": existing.get("written") or [],
        "seals": existing.get("seals") or [],
        "canon_standing": standing["canon_standing"],
        "canon_score": standing["canon_score"],
        "drift_flags": standing["drift_flags"],
        "promotion_candidate": standing["promotion_candidate"],
        "chi_factor": classification.get("chi_factor"),
        "chi": classification.get("chi") or {},
        "law": classification.get("law") or {},
        "keyword_registry": str(STATE_REGISTRY) if STATE_REGISTRY.exists() else None,
        "boundary": "Sidecar metadata only. It does not alter, admit, move, or canonize the source file.",
    }
    return payload


def maybe_write_canon_sidecar(source: Path, classification: dict, standing: dict, identity: dict) -> Path | None:
    """Write .canon.sidecar.json only when standing trips lossless — keeps scans fast."""
    cfg = load_config()
    if not cfg.get("write_canon_sidecar_on_trigger") or not standing.get("lossless_trigger"):
        return None
    target = Path(str(source) + ".canon.sidecar.json")
    if target.exists():
        # Never overwrite a human sidecar; merge score fields only if we created it.
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if current.get("created_by") != "David-OS v3 FIS scanner":
            return None
    payload = build_canon_sidecar(source, classification, standing, identity)
    try:
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return target


def make_action_proposal(
    *,
    action_type: str,
    target: Path | str,
    before: str,
    after: str,
    score: float,
    rule_id: str,
    extra: dict | None = None,
) -> dict:
    """Universal approval object from hub-overview.md. Propose only."""
    entry = {
        "schema": "action_proposal.v1",
        "type": action_type,
        "target": str(target),
        "before": before,
        "after": after,
        "score": round(float(score or 0), 4),
        "rule_id": rule_id,
        "ts": utc_now(),
    }
    if extra:
        entry.update(extra)
    return entry
