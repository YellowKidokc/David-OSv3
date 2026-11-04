"""Stage 2B classification sidecar writer.

Usage:
  python -m engine.sidecar_writer generate PATH [--dry-run] [--me-enrich]

This worker records proposals. It never renames, moves, deletes, quarantines or
changes canon/admission authority.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import config as pipeline_config
sys.modules["config"] = pipeline_config

# The preserved pipeline modules historically use sibling imports. Alias each
# dependency before importing the next package; the underlying logic is unchanged.
from engine import chi as pipeline_chi
sys.modules["chi"] = pipeline_chi
from engine import tagger as pipeline_tagger
sys.modules["tagger"] = pipeline_tagger
from engine import preference as pipeline_preference
sys.modules["preference"] = pipeline_preference
from engine import preference_engine as pipeline_preference_engine
sys.modules["preference_engine"] = pipeline_preference_engine

from engine import canon_sidecar, domain_classifier, rename_planner, smart_tagger, text_extractor
from engine.me_rename_bridge import add_name_context, read_intake, update_work
from engine.stage2b_common import (
    DEFAULT_DB,
    atomic_json,
    admission_for,
    connect_registry,
    dump,
    migrate_stage2b,
    now,
    source_fingerprint,
    table_exists,
)

OWNED_FIELDS = {
    "schema_version", "work_id", "series_code", "nabla_address", "domain", "tags",
    "chi_score", "canon_status", "proposed_name", "rename_approved", "rename_decision",
    "rename_score", "timestamp", "source", "admission", "me_variables", "me_primary",
    "me_lane", "me_contamination", "_generated_snapshot",
    "me_reference",
}


def _read_text(path: Path) -> str:
    try:
        return text_extractor.extract_text(str(path), limit=200_000) or ""
    except Exception:
        return ""


def _record(file_row, text: str) -> pipeline_config.FileRecord:
    path = Path(file_row["path"])
    rec = pipeline_config.FileRecord(
        path=str(path),
        name=path.name,
        extension=path.suffix.lower(),
        size_bytes=int(file_row["size"] or 0),
        sha256=file_row["sha256"] or "",
        modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        source_root=file_row["root"],
        content_preview=text[:4000],
    )
    domain_classifier.classify(rec, text)
    rename_planner.plan_name(rec, text)
    return rec


def _canon_status(source: Path, admission: dict[str, Any], ruled_status: str | None) -> str:
    if ruled_status in {"canonical", "duplicate", "variant"}:
        return ruled_status
    own = canon_sidecar.sidecar_path(source)
    if own.exists():
        return "canonical"
    source_value = str(source)
    for sidecar in source.parent.glob("*.canon.json"):
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            versions = payload.get("versions") or []
            if any(item.get("path") == source_value for item in versions if isinstance(item, dict)):
                relation = admission.get("family_relation")
                return "duplicate" if relation in {"exact_duplicate", "byte_duplicate"} else "variant"
        except (OSError, json.JSONDecodeError):
            continue
    return "unresolved"


def _merge_existing(existing: dict[str, Any], generated: dict[str, Any], *, force: bool) -> dict[str, Any]:
    if force:
        return generated
    previous = existing.get("_generated_snapshot")
    result = dict(existing)
    human_overrides: dict[str, Any] = {}
    if isinstance(previous, dict):
        for key in OWNED_FIELDS:
            if key in existing and key in previous and existing[key] != previous[key]:
                human_overrides[key] = existing[key]
    else:
        # An older/unmanaged sidecar may contain human-authored values. Preserve
        # overlapping fields on the first managed merge.
        human_overrides = {key: existing[key] for key in OWNED_FIELDS if key in existing}
    result.update(generated)
    result.update(human_overrides)
    result["_generated_snapshot"] = {
        key: value for key, value in generated.items() if key != "_generated_snapshot"
    }
    return result


def _query_rows(con, root: Path, work_id: str | None) -> list[Any]:
    clauses = ["f.present=1"]
    params: list[Any] = []
    if work_id:
        clauses.append("w.work_id=?")
        params.append(work_id)
    rows = con.execute(
        """
        SELECT f.*, v.work_id, w.series_code, w.display_code, w.domain AS work_domain,
               w.tags_json AS work_tags_json, w.canon_status AS work_canon_status,
               n.address AS nabla_address, n.status AS nabla_status
        FROM files f
        LEFT JOIN versions v ON v.version_id=f.version_id
        LEFT JOIN works w ON w.work_id=v.work_id
        LEFT JOIN nabla n ON n.version_id=f.version_id
        WHERE """ + " AND ".join(clauses) + " ORDER BY f.path",
        params,
    ).fetchall()
    return [row for row in rows if Path(row["path"]).resolve().is_relative_to(root)]


def generate(
    root: str | Path,
    *,
    db_path: str | Path = DEFAULT_DB,
    dry_run: bool = False,
    force: bool = False,
    work_id: str | None = None,
    report: bool = False,
    me_enrich: bool = False,
    me_intake_db: str | Path | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)
    run_id = uuid.uuid4().hex
    stats: dict[str, Any] = {
        "run_id": run_id, "files_processed": 0, "sidecars_created": 0,
        "sidecars_updated": 0, "unchanged_skipped": 0, "errors": [], "previews": [],
        "dry_run": dry_run,
    }
    with connect_registry(db_path, migrate=not dry_run) as con:
        if not table_exists(con, "admission"):
            raise ValueError("Stage 2A admission table is missing")
        for row in _query_rows(con, root_path, work_id):
            source = Path(row["path"])
            if source.name.endswith((".fis.json", ".canon.json")):
                continue
            try:
                admission = admission_for(con, row)
                me = read_intake(me_intake_db, source) if me_enrich and me_intake_db else {}
                fingerprint = source_fingerprint(row, admission, me=me)
                sidecar = Path(str(source) + ".fis.json")
                if (
                    not force
                    and "sidecar_source_fingerprint" in row.keys()
                    and row["sidecar_source_fingerprint"] == fingerprint
                    and sidecar.exists()
                ):
                    stats["unchanged_skipped"] += 1
                    continue

                text = _read_text(source)
                rec = _record(row, text)
                smart_tags = list(smart_tagger.smart_tag_file(str(source), text, source.name, {}))
                proposed_name = add_name_context(rec.proposed_name, me.get("me_primary"))
                # Import and use canon-sidecar's source description rather than
                # creating a second hash/metadata implementation.
                described = canon_sidecar.describe(source)
                payload: dict[str, Any] = {
                    "schema_version": "fis-sidecar/v1",
                    "work_id": row["work_id"],
                    "series_code": row["display_code"] or row["series_code"],
                    "nabla_address": row["nabla_address"],
                    "domain": rec.domain,
                    "tags": smart_tags,
                    "chi_score": rec.chi_confidence,
                    "canon_status": _canon_status(source, admission, row["work_canon_status"]),
                    "proposed_name": proposed_name,
                    "rename_approved": False,
                    "rename_decision": rec.decision,
                    "rename_score": rec.confidence,
                    "timestamp": now(),
                    "source": described,
                    "admission": admission,
                    **me,
                }
                payload["_generated_snapshot"] = {
                    key: value for key, value in payload.items() if key != "_generated_snapshot"
                }
                if sidecar.exists():
                    existing = json.loads(sidecar.read_text(encoding="utf-8"))
                    if not isinstance(existing, dict):
                        raise ValueError("Existing sidecar must contain a JSON object")
                    payload = _merge_existing(existing, payload, force=force)
                    action = "sidecars_updated"
                else:
                    action = "sidecars_created"

                stats["files_processed"] += 1
                stats["previews"].append({"source": str(source), "sidecar": str(sidecar), "payload": payload})
                if dry_run:
                    continue
                atomic_json(sidecar, payload)
                con.execute(
                    "UPDATE files SET sidecar_written=?, sidecar_source_fingerprint=? WHERE path=?",
                    (now(), fingerprint, str(source)),
                )
                if me:
                    update_work(con, row["version_id"], me)
                stats[action] += 1
            except Exception as exc:
                stats["errors"].append({"path": str(source), "error": str(exc)})
        if not dry_run:
            con.commit()

    if report:
        report_path = Path(db_path).resolve().parent / "sidecar_report.md"
        lines = [
            "# Stage 2B Sidecar Report", "",
            f"- Run: `{run_id}`", f"- Dry run: `{dry_run}`",
            f"- Files processed: {stats['files_processed']}",
            f"- Sidecars created: {stats['sidecars_created']}",
            f"- Sidecars updated: {stats['sidecars_updated']}",
            f"- Unchanged skipped: {stats['unchanged_skipped']}",
            f"- Errors: {len(stats['errors'])}", "",
        ]
        lines.extend(f"- `{item['path']}`: {item['error']}" for item in stats["errors"])
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        stats["report"] = str(report_path)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("generate")
    command.add_argument("path", type=Path)
    command.add_argument("--db", type=Path, default=DEFAULT_DB)
    command.add_argument("--dry-run", action="store_true")
    command.add_argument("--force", action="store_true")
    command.add_argument("--work-id")
    command.add_argument("--report", action="store_true")
    command.add_argument("--me-enrich", action="store_true")
    command.add_argument("--me-intake-db", type=Path)
    args = parser.parse_args(argv)
    if args.me_enrich and not args.me_intake_db:
        parser.error("--me-enrich requires --me-intake-db")
    result = generate(
        args.path, db_path=args.db, dry_run=args.dry_run, force=args.force,
        work_id=args.work_id, report=args.report, me_enrich=args.me_enrich,
        me_intake_db=args.me_intake_db,
    )
    print(dump(result))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

