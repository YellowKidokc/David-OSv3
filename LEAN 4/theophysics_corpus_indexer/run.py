"""End-to-end P1-P2 pipeline for the Theophysics corpus indexer."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2

from classifier import classify
from config import (
    BATCH_RUNS_DIR,
    CONFIG_HASH,
    MANIFEST_CSV,
    MASTER_LIST_CSV,
    REGISTRY_JSON,
    project_dir,
)
from db import (
    compute_verif_levels,
    get_conn,
    get_p1_metrics,
    get_p2_metrics,
    get_spot_check,
    init_schema,
    insert_declaration,
    insert_location,
    insert_receipt,
    reset_corpus_tables,
    upsert_file,
)
from inventory import scan_roots
from loaders import load_batch_runs, load_manifest, load_master_list, load_registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _manifest_counts(entry: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if entry is None:
        return None, None
    decl_count = entry.get("theorems")
    sorry_active = entry.get("active_sorry")
    return decl_count, sorry_active


def _title_from_registry(sha: str, registry: dict[str, dict[str, Any]]) -> str:
    rec = registry.get(sha)
    if rec:
        return rec.get("title", "") or ""
    return ""


def _title_from_master_list(sha: str, master_list: list[dict[str, Any]]) -> str:
    for row in master_list:
        if row["sha256"] == sha and row.get("paper"):
            return row["paper"]
    return ""


def _resolve_prefix(
    prefix: str, sha_to_paths: dict[str, set[str]]
) -> list[str]:
    """Resolve a 16-char sha prefix to full shas using the scanned corpus."""
    return [sha for sha in sha_to_paths if sha.startswith(prefix.lower())]


def main() -> int:
    parser = argparse.ArgumentParser(description="Theophysics corpus indexer P1-P2")
    parser.add_argument("--reset", action="store_true", help="Drop corpus tables before run")
    parser.add_argument("--batch-size", type=int, default=1000, help="DB flush batch size")
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    logger.info("Run started at %s", started.isoformat())
    logger.info("Config hash: %s", CONFIG_HASH)

    # ------------------------------------------------------------------
    # Load existing records first (do not recompute what they state)
    # ------------------------------------------------------------------
    logger.info("Loading manifest...")
    manifest = load_manifest(MANIFEST_CSV)
    logger.info("Manifest records: %d", len(manifest))

    logger.info("Loading registry...")
    registry = load_registry(REGISTRY_JSON)
    logger.info("Registry records: %d", len(registry))

    logger.info("Loading master list...")
    master_list = load_master_list(MASTER_LIST_CSV)
    logger.info("Master list rows: %d", len(master_list))

    logger.info("Loading batch runs...")
    batch_records = load_batch_runs(BATCH_RUNS_DIR)
    logger.info("Batch run records: %d", len(batch_records))

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------
    conn = get_conn()
    if args.reset:
        logger.info("Resetting corpus tables...")
        reset_corpus_tables(conn)
    init_schema(conn)

    # ------------------------------------------------------------------
    # Scan, classify, insert
    # ------------------------------------------------------------------
    sha_to_paths: dict[str, set[str]] = {}
    sha_best: dict[str, dict[str, Any]] = {}
    file_buffer: list[dict[str, Any]] = []
    loc_buffer: list[tuple[str, str]] = []
    decl_buffer: list[tuple[str, str, str]] = []

    def _best_summary(sha: str, path: str, content_summary: str) -> str:
        title = _title_from_registry(sha, registry) or _title_from_master_list(sha, master_list)
        if title:
            return title
        if content_summary:
            return content_summary
        return Path(path).name

    def flush() -> None:
        if not (file_buffer or loc_buffer or decl_buffer):
            return
        with conn.cursor() as cur:
            for rec in file_buffer:
                upsert_file(cur, **rec)
            if loc_buffer:
                cur.executemany(
                    """
                    INSERT INTO locations (sha256, path) VALUES (%s, %s)
                    ON CONFLICT (sha256, path) DO NOTHING
                    """,
                    loc_buffer,
                )
            if decl_buffer:
                cur.executemany(
                    """
                    INSERT INTO declarations (sha256, name, kind) VALUES (%s, %s, %s)
                    ON CONFLICT (sha256, name) DO NOTHING
                    """,
                    decl_buffer,
                )
        conn.commit()
        file_buffer.clear()
        loc_buffer.clear()
        decl_buffer.clear()

    total_scanned = 0
    for item in scan_roots(manifest=manifest):
        total_scanned += 1
        path = item["path"]
        sha = item["sha256"]
        ext = item["ext"]
        text = item["text"]
        manifest_entry = item["manifest_entry"]

        sha_to_paths.setdefault(sha, set()).add(path)

        series, conf, is_library, parsed_decl_count, parsed_sorry, decls, content_summary = classify(
            path, ext, text
        )

        # Use manifest counts when available, otherwise parsed counts.
        manifest_decl, manifest_sorry = _manifest_counts(manifest_entry)
        decl_count = manifest_decl if manifest_decl is not None else parsed_decl_count
        sorry_active = manifest_sorry if manifest_sorry is not None else parsed_sorry

        # Aggregate classification across all locations for this SHA.
        best = sha_best.setdefault(
            sha,
            {
                "sha256": sha,
                "ext": ext,
                "size_bytes": item["size"],
                "first_seen": item["mtime"],
                "series": None,
                "series_conf": 0.0,
                "decl_count": decl_count,
                "sorry_active": sorry_active,
                "is_library": False,
                "summary": _best_summary(sha, path, content_summary),
            },
        )
        # Keep the earliest first_seen.
        if item["mtime"] < best["first_seen"]:
            best["first_seen"] = item["mtime"]
        # Library quarantine is irreversible; otherwise take the first non-null series.
        if is_library:
            best["is_library"] = True
            best["series"] = "LIBRARY"
            best["series_conf"] = 1.0
        elif series is not None and best["series"] is None:
            best["series"] = series
            best["series_conf"] = conf
        # Prefer manifest/parsed counts once set; decl_count from manifest wins.
        if manifest_decl is not None:
            best["decl_count"] = manifest_decl
        elif best["decl_count"] is None:
            best["decl_count"] = parsed_decl_count
        if manifest_sorry is not None:
            best["sorry_active"] = manifest_sorry
        elif best["sorry_active"] is None:
            best["sorry_active"] = parsed_sorry

        file_buffer.append(best)
        loc_buffer.append((sha, path))
        for kind, name in decls:
            decl_buffer.append((sha, name, kind))

        if len(file_buffer) >= args.batch_size:
            flush()
            if total_scanned % 5000 == 0:
                logger.info("Scanned %d files...", total_scanned)

    # Final flush for any remaining rows.
    if file_buffer:
        flush()
    logger.info("Scan complete: %d file locations indexed", total_scanned)

    # ------------------------------------------------------------------
    # Insert receipts
    # ------------------------------------------------------------------
    with conn.cursor() as cur:
        # AI_REVIEW receipts from registry.json
        for sha, rec in registry.items():
            insert_receipt(
                cur,
                sha,
                rec["record_id"],
                "AI_REVIEW",
                rec["status"],
                rec.get("output_dir"),
                rec.get("ran_at"),
            )

        # BUILD / PRINT_AXIOMS receipts from batch runs.
        for rec in batch_records:
            sha = rec["sha256"]
            if len(sha) == 16:
                candidates = _resolve_prefix(sha, sha_to_paths)
                if not candidates:
                    logger.warning("Batch receipt prefix %s not resolved to a scanned file; skipping", sha)
                    continue
                if len(candidates) > 1:
                    logger.warning(
                        "Batch receipt prefix %s is ambiguous (%d matches); skipping",
                        sha,
                        len(candidates),
                    )
                    continue
                sha = candidates[0]
            insert_receipt(
                cur,
                sha,
                rec["run_id"],
                rec["kind"],
                rec["result"],
                rec.get("log_path"),
                rec.get("ran_at"),
            )
    conn.commit()

    # ------------------------------------------------------------------
    # Compute verification levels and report
    # ------------------------------------------------------------------
    compute_verif_levels(conn)

    with conn.cursor() as cur:
        p1 = get_p1_metrics(cur)
        p2 = get_p2_metrics(cur)
        spot_check = get_spot_check(cur, limit=50)

    finished = datetime.now(timezone.utc)

    receipt = {
        "run_id": started.strftime("%Y-%m-%dT%H%M%S"),
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "config_hash": CONFIG_HASH,
        "p1": p1,
        "p2": p2,
    }

    receipts_dir = project_dir() / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{receipt['run_id']}-receipt.json"
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, default=str)
    logger.info("Receipt written to %s", receipt_path)

    spot_path = project_dir() / "spot_check.csv"
    with spot_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sha256", "path", "series", "series_conf", "verif_level",
                "decl_count", "sorry_active", "summary",
            ],
        )
        writer.writeheader()
        writer.writerows(spot_check)
    logger.info("Spot-check sheet written to %s", spot_path)

    # P1 gate
    print("\n=== P1 INVENTORY GATE ===")
    print(f"Total locations scanned: {p1['total_locations']}")
    print(f"Unique files (SHA-256):  {p1['unique_files']}")
    print(f"Duplicate hashes:        {p1['duplicate_hashes']} ({p1['duplicate_ratio']:.2%})")
    print("Per-root:")
    for root, count in sorted(p1["per_root"].items()):
        print(f"  {root}: {count}")
    print("Per-extension:")
    for ext, count in sorted(p1["per_ext"].items(), key=lambda x: -x[1]):
        print(f"  {ext}: {count}")

    # P2 gate
    print("\n=== P2 CLASSIFICATION GATE ===")
    total = p2["total"]
    print(
        f"{total} unique files: "
        f"{p2['classified_pct']}% classified at >=0.8 confidence, "
        f"{p2['library_pct']}% LIBRARY quarantined, "
        f"{p2['unclassified_pct']}% unclassified, "
        f"{p2['with_receipt_pct']}% carrying a receipt above AI_REVIEW."
    )
    print("Series counts:")
    for series, count in sorted(p2["series_counts"].items(), key=lambda x: -x[1]):
        print(f"  {series}: {count}")

    conn.close()
    logger.info("Run finished at %s", finished.isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
