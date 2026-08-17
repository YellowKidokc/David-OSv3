"""
rename_planner.py — PROPOSE-ONLY name generator.

Builds the canonical name  DOMAIN__CT__tag1-tag2__YYYYMMDD__ST.ext  from a
classified FileRecord, asks the preference engine whether it would auto-approve,
and records the proposal. It NEVER touches the file — applying renames is a
separate, later worker. Spliced from FIS\fis_namer.py.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import config
import tagger
from preference_engine import get_engine

_NR = config.NAMING
CT_CODES = {
    "document": "DOC", "code": "COD", "data": "DAT", "note": "NOT",
    "config": "CFG", "paper": "PAP", "image": "IMG", "video": "VID",
    "audio": "AUD", "binary": "BIN",
}
STATUS_CODES = {"draft": "DR", "active": "AC", "final": "FN", "archive": "AR", "review": "RV"}

AUTO_APPROVE = float(_NR.get("auto_approve_threshold", 0.72))
QUEUE        = float(_NR.get("queue_threshold", 0.45))
SEP          = _NR.get("separator", "__")
TAGSEP       = _NR.get("tag_separator", "-")

# Extensions whose content type is certain without reading the file.
_EXT_CERTAIN = {
    ".py", ".js", ".ts", ".ahk", ".json", ".csv", ".sqlite", ".db",
    ".md", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac",
}


def plan_name(rec: "config.FileRecord", text: str = "") -> None:
    """Mutates rec.proposed_name / decision / reason in place. Read-only on disk."""
    ext = rec.extension.lower()
    conf = rec.confidence or 0.0

    domain_code = rec.domain or "GN"
    ct_code = CT_CODES.get((rec.content_type or "").lower(), "DOC")
    status_code = STATUS_CODES.get((rec.status or "").lower(), "AC")
    tags = tagger.extract_tags(rec.name, text)
    rec.tags = tags
    rec.topic_slug = tagger.topic_slug(rec.name)

    mtime = _mtime(rec)
    date_str = datetime.fromtimestamp(mtime).strftime(_NR.get("date_format", "%Y%m%d")) \
        if mtime else "00000000"

    ext_known = ext in _EXT_CERTAIN
    has_text = bool(text and text.strip())
    # Skip only when we truly can't say anything: low confidence, unknown ext,
    # AND no readable text. Readable low-confidence files still get a provisional
    # proposal + queue so the enricher can rescue them from similar files.
    if conf < QUEUE and not ext_known and not has_text:
        rec.decision = "skip"
        rec.reason = f"confidence {conf:.2f}, unknown ext {ext}, no readable text"
        rec.proposed_name = None
        return

    tag_str = TAGSEP.join(tags) if tags else "GN"
    proposed = f"{domain_code}{SEP}{ct_code}{SEP}{tag_str}{SEP}{date_str}{SEP}{status_code}{ext}"
    proposed = proposed[:int(_NR.get("max_filename_length", 180))]
    rec.proposed_name = proposed

    proposal = {
        "proposed_name": proposed, "domain_code": domain_code,
        "ct_code": ct_code, "status_code": status_code, "tags": tags,
    }

    engine = get_engine()
    if engine.n_seen >= engine.MIN_SAMPLES:
        ok, reason = engine.should_auto_approve(proposal, conf, AUTO_APPROVE)
        decision = "auto_approve" if ok else "queue"
    elif conf >= AUTO_APPROVE or ext_known:
        decision = "auto_approve"
        reason = (f"conf={conf:.2f}>={AUTO_APPROVE}" if conf >= AUTO_APPROVE else "ext-certain")
    else:
        decision = "queue"
        reason = f"conf={conf:.2f} below threshold"

    rec.decision = decision
    rec.reason = reason


def _mtime(rec) -> float:
    try:
        return Path(rec.path).stat().st_mtime
    except Exception:
        return 0.0
