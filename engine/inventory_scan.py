"""
inventory_scan.py — the pipeline spine.

walk roots -> fingerprint (identity) -> extract text -> classify (5 tags + chi)
-> plan name (propose-only) -> upsert SQLite -> append JSONL ledger. Also infers
copy/move/modify from content hash, and detects folder-level symptoms.

NOTHING on disk is renamed, moved, or deleted. This only observes and proposes.
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import config
import fingerprint as fp
import text_extractor
import domain_classifier
import rename_planner
import metadata_db as db
import ledger
import enricher as enricher_mod
import capability
from category_markov import CategoryMarkov


def _should_skip_dir(name: str) -> bool:
    return name in set(config.IGNORE.get("skip_dirs", []))


def _should_skip_file(p: Path, file_types: List[str]) -> bool:
    ext = p.suffix.lower()
    if ext in set(config.IGNORE.get("skip_exts", [])):
        return True
    if p.name.lower() in set(config.IGNORE.get("skip_names", [])):
        return True
    if file_types and ext not in file_types:
        return True
    return False


def _infer_event(con, sha256: str, path: str) -> str:
    """created | modified | probable_copy | probable_move based on hash + prior state."""
    prior_same_path = db.get_one(con, path)
    if prior_same_path is not None:
        return "modified" if prior_same_path["sha256"] != sha256 else "rescanned"
    twins = db.get_by_hash(con, sha256, exclude_path=path)
    if twins:
        # same content elsewhere: copy if the twin still exists, else a move
        for t in twins:
            if Path(t["path"]).exists():
                return "probable_copy"
        return "probable_move"
    return "created"


def scan(cfg: config.ScanConfig,
         progress_cb: Optional[Callable[[int, str], None]] = None
         ) -> Tuple[List[config.FileRecord], dict, dict]:
    con = db.connect(cfg.db_path)
    run_id = db.start_run(con, cfg.scan_roots, cfg.file_types)
    enr = enricher_mod.Enricher(con, cfg.reference_db) if cfg.enrich else None
    registry = (capability.CapabilityRegistry.load_or_default(
        str(config.CONFIG_DIR / "capability.json")) if cfg.gate else None)

    records: List[config.FileRecord] = []
    by_folder: dict = defaultdict(list)
    count = 0
    enriched_n = 0
    smoothed_n = 0

    for root in cfg.scan_roots:
        root_path = Path(root)
        if not root_path.exists():
            ledger.log_error("inventory_scan", "root does not exist", path=str(root))
            print(f"WARNING: scan root does not exist: {root}")
            continue

        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
            for fn in filenames:
                p = Path(dirpath) / fn
                if _should_skip_file(p, cfg.file_types):
                    continue
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                if size < cfg.min_file_size or size > cfg.max_file_size:
                    continue

                try:
                    fpr = fp.fingerprint(str(p))
                except Exception as e:
                    ledger.log_error("inventory_scan", f"fingerprint failed: {e}", path=str(p))
                    continue

                rec = config.FileRecord(
                    path=fpr["path"], name=fpr["name"], extension=fpr["extension"],
                    size_bytes=fpr["size_bytes"], sha256=fpr["sha256"],
                    modified_at=fpr["modified_at"], created_at=fpr["created_at"],
                    source_root=str(root),
                )

                event = _infer_event(con, rec.sha256, rec.path)
                ledger.log_event(event, rec.path, sha256=rec.sha256, size=rec.size_bytes)

                text = text_extractor.extract_text(rec.path, cfg.content_preview_chars * 50)
                rec.content_preview = (text or "")[:cfg.content_preview_chars]
                rec.fuzzy_hash = fp.simhash(text) if text else ""

                domain_classifier.classify(rec, text)
                rename_planner.plan_name(rec, text)

                # low-confidence path: enrich from similar already-classified files
                if enr is not None and rec.proposed_name:
                    enrichment = enr.maybe_enrich(rec)
                    if enrichment and enrichment.get("outcome") == "enriched":
                        enriched_n += 1
                        ledger.log_event("enriched", rec.path,
                                         best_sim=enrichment.get("best_sim"),
                                         suggested_domain=enrichment.get("suggested_domain"))

                # capability gate: subject category + access tier + processing route
                if registry is not None:
                    res = capability.gate_record(rec, registry)   # also stamps rec.notes
                    rec.gate_category = res.category
                    rec.gate_tier = res.tier
                    rec.gate_route = res.route
                    rec.gate_access = res.access
                    if res.route == capability.ROUTE_BLOCK:
                        ledger.log_event("gate_blocked", rec.path, category=res.category,
                                         needs=res.required_sources)

                ledger.log_event("classified", rec.path, domain=rec.domain,
                                 content_type=rec.content_type, confidence=rec.confidence,
                                 decision=rec.decision)

                if cfg.store_db:
                    db.upsert_file(con, rec.to_dict())
                    if rec.proposed_name:
                        ledger.log_rename("proposed", rec.name, rec.proposed_name,
                                          decision=rec.decision, reason=rec.reason)

                records.append(rec)
                by_folder[str(p.parent)].append(rec)
                count += 1
                if cfg.commit_every and count % cfg.commit_every == 0:
                    con.commit()          # persist incrementally; release the write lock
                if progress_cb and count % 50 == 0:
                    progress_cb(count, str(p))
                if cfg.max_files and count >= cfg.max_files:
                    break
            if cfg.max_files and count >= cfg.max_files:
                break
        if cfg.max_files and count >= cfg.max_files:
            break

    # folder category-Markov: fill in `uncategorized` files from their neighbours
    if registry is not None and records:
        cmarkov = CategoryMarkov()
        for folder, frecs in by_folder.items():
            ordered = sorted(frecs, key=lambda r: r.name)
            cmarkov.learn_sequence([r.gate_category or "uncategorized" for r in ordered])
            prev = None
            for r in ordered:
                if (r.gate_category in (None, "uncategorized")) and prev:
                    pred, prob = cmarkov.predict_next(prev)
                    if pred and pred != "uncategorized" and prob >= 0.5:
                        entry = registry.get(pred)
                        route, _ = entry.resolve_route()
                        r.gate_category, r.gate_tier = pred, entry.tier
                        r.gate_route, r.gate_access = route, entry.access
                        r.notes = (r.notes or "") + f" [GATE-MARKOV {pred}<-{prev} p={prob:.2f}]"
                        if cfg.store_db:
                            db.upsert_file(con, r.to_dict())
                        smoothed_n += 1
                prev = r.gate_category
        cmarkov.save()

    db.finish_run(con, run_id, count)
    con.commit()
    if enr is not None:
        enr.close()
    con.close()

    folder_symptoms = {folder: detect_folder_symptoms(folder, recs)
                       for folder, recs in by_folder.items()}
    folder_symptoms = {k: v for k, v in folder_symptoms.items() if v}

    needs_access: dict = {}
    if registry is not None:
        for r in records:
            if r.gate_route == capability.ROUTE_BLOCK:
                na = needs_access.setdefault(r.gate_category, [])
                for s in registry.get(r.gate_category).required_sources:
                    if s not in na:
                        na.append(s)

    summary = {
        "file_count": count,
        "domains": dict(Counter(r.domain for r in records)),
        "content_types": dict(Counter(r.content_type for r in records)),
        "decisions": dict(Counter(r.decision for r in records)),
        "enriched": enriched_n,
        "folders_with_symptoms": len(folder_symptoms),
        "gate_routes": dict(Counter(r.gate_route for r in records if r.gate_route)),
        "gate_tiers": dict(Counter(r.gate_tier for r in records if r.gate_tier)),
        "gate_smoothed": smoothed_n,
        "needs_access": needs_access,
    }
    return records, folder_symptoms, summary


# --------------------------------------------------------------------------- #
# Folder symptom detectors (subset of the 20-symptom registry)
# --------------------------------------------------------------------------- #
def detect_folder_symptoms(folder: str, recs: List[config.FileRecord]) -> List[str]:
    out = []
    n = len(recs)
    if n == 0:
        return out
    exts = Counter(r.extension for r in recs)
    hashes = Counter(r.sha256 for r in recs)
    stems = Counter(_version_stem(r.name) for r in recs)

    # S01 Extension swamp: many distinct extensions in one folder
    if len(exts) >= 6:
        out.append("S01")
    # S04 Flat overload: too many files directly in one folder
    if n >= 200:
        out.append("S04")
    # S02 Version sprawl: same base name with v1/v2/copy/final variants
    if any(c >= 3 for c in stems.values()):
        out.append("S02")
    # C01 Duplicate cluster: identical content hashes repeated
    if any(c >= 2 for c in hashes.values()):
        out.append("C01")
    # C05 Media dump: dominated by image/video/audio
    media = sum(1 for r in recs if r.content_type in ("image", "video", "audio"))
    if n >= 10 and media / n >= 0.7:
        out.append("C05")
    # C04 Document chaos: lots of docs, no naming structure
    docs = sum(1 for r in recs if r.content_type in ("document", "note", "paper"))
    if n >= 25 and docs / n >= 0.6:
        out.append("C04")
    return out


_VER = __import__("re").compile(r"[\s_\-]*(v?\d+|copy|final|draft|old|new|bak)\b", __import__("re").I)


def _version_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    return _VER.sub("", stem).strip()
