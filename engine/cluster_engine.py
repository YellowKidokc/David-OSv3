"""
cluster_engine.py — reversible cluster discovery and manifest planning.

This module sits above the David-OS file intelligence primitives.  It scans
candidate source folders and a canonical target tree, fingerprints documents,
groups likely relatives, scores cluster confidence separately from action
safety, applies kill-condition gates, and writes review manifests.

Central axiom: membership inference and action authority are not the same thing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import domain_classifier
import fingerprint as fp_mod
import tagger
import text_extractor

try:  # optional near-dup helpers; keep the engine usable without them
    import fis_near_dup  # type: ignore
except Exception:  # pragma: no cover - optional module may not exist
    fis_near_dup = None

SUPPORTED_EXTENSIONS = {".html", ".htm", ".md", ".lean", ".pdf", ".docx"}
PROVENANCE_PENALTY_WORDS = {"staging", "draft", "work", "temp", "tmp", "old", "backup", "bak"}
PROTECTED_ROOT_MARKERS = {".git", "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml"}
READING_LAYERS = {"story", "highschool", "college", "phd", "doctoral", "technical", "reading_layers"}
KNOWN_TARGET_FOLDERS = [
    "isomorphism", "genesis-to-quantum", "moral-decline", "convergence-series",
    "convergence-deep", "lean4", "master-equation", "Axiom Layer", "proof-explorer",
    "proof-architecture", "rigor", "logos-papers", "one-page-stories", "consciousness",
    "the-bidirectional-audit", "blue", "glossary", "cross-domain", "three-truths",
    "three-gates", "formal-papers", "duality-project", "revolution-of-truth",
    "mda", "equation", "Family", "Constitutional audit", "assets", "components",
    "shared", "notebooklm_text", "notebooklm_downloads", "Templates David", "Templeton",
    "work", "MUST DO",
]
ALIASES = {"mda": "moral-decline", "equation": "master-equation"}
WEIGHTS = {"F": 3, "N": 4, "E": 1, "C": 2, "H": 5, "T": 1, "P": 1, "Role": 2}


@dataclass
class SectionUnit:
    section_id: str
    heading: str
    level: int
    word_count: int
    paragraph_hashes: List[str]
    section_hash: str


@dataclass
class DocumentFingerprint:
    identity: Dict[str, Any]
    structural_tree: Dict[str, Any]
    semantic_profile: Dict[str, Any]
    provenance: Dict[str, Any]
    sparse_anchors: Dict[str, Any]
    integrity: Dict[str, Any]


@dataclass
class FileEntry:
    path: str
    source_root: str
    relative_path: str
    folder_key: str
    fingerprint: Dict[str, Any]
    text_preview: str
    tags: List[str]
    classification: Dict[str, Any]
    sparse_fingerprint: Dict[str, Any]
    document_fingerprint: Dict[str, Any]
    simhash: str


@dataclass
class CandidateCluster:
    cluster_id: str
    source_folder: str
    target_folder: str
    files: List[str]
    score_components: Dict[str, float]
    raw_score: float
    cluster_confidence: int
    action_safety: int
    rival_margin: float
    cluster_type: str
    kill_conditions: List[str]
    behavior: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text or "")
    return [p.strip() for p in parts if p.strip()]


def heading_skeleton(text: str) -> List[str]:
    heads: List[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        m = re.match(r"^(#{1,3})\s+(.+)$", s)
        if m:
            heads.append(m.group(2).strip()[:120])
            continue
        if re.match(r"(?i)^<h[1-3][^>]*>.*</h[1-3]>", s):
            heads.append(re.sub(r"<[^>]+>", "", s).strip()[:120])
    return heads[:100]


def sparse_sentence_fingerprint(text: str) -> Dict[str, Any]:
    sentences = split_sentences(text)
    return {
        "word_count": len(re.findall(r"\b\w+\b", text or "")),
        "first_sentence": (sentences[0] if sentences else "")[:100],
        "every_20th_sentence": [sentences[i][:80] for i in range(19, len(sentences), 20)],
        "last_sentence": (sentences[-1] if sentences else "")[:100],
        "heading_skeleton": heading_skeleton(text),
    }


def build_sections(text: str) -> Tuple[List[SectionUnit], str]:
    sections: List[Tuple[str, int, List[str]]] = [("root", 0, [])]
    for line in (text or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m and len(m.group(1)) <= 3:
            sections.append((m.group(2).strip(), len(m.group(1)), []))
        else:
            sections[-1][2].append(line)
    units: List[SectionUnit] = []
    for idx, (heading, level, lines) in enumerate(sections):
        body = "\n".join(lines).strip()
        paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()] or ([body] if body else [])
        ph = [sha256_text(normalize_text(p)) for p in paragraphs]
        sh = sha256_text("|".join(ph))
        sid = "section:" + re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") + f":{idx}"
        units.append(SectionUnit(sid, heading, level, len(re.findall(r"\b\w+\b", body)), ph, sh))
    root = sha256_text("|".join(u.section_hash for u in units))
    return units, root


def provenance_for(path: Path, classification: Dict[str, Any]) -> Dict[str, Any]:
    low = str(path).lower()
    purpose = "working_draft" if any(w in low for w in PROVENANCE_PENALTY_WORDS) else "preservation_candidate"
    return {
        "who": {"value": "unknown", "confidence": 0.0, "source_class": "unknown"},
        "what": {"value": path.stem, "confidence": 0.55, "source_class": "filename"},
        "when": {"value": classification.get("date", ""), "confidence": 0.45, "source_class": "metadata"},
        "where": {"value": str(path.parent), "confidence": 0.7, "source_class": "contextual"},
        "why": {
            "author_intent": {"value": "unknown", "confidence": 0.0, "source_class": "unknown"},
            "document_purpose": {"value": classification.get("content_type", "unknown"), "confidence": 0.45, "source_class": "structural"},
            "workflow_purpose": {"value": purpose, "confidence": 0.55, "source_class": "contextual"},
            "routing_reason": {"value": "cluster_scan", "confidence": 1.0, "source_class": "inferred"},
            "preservation_reason": {"value": "never_delete_unique_hashes", "confidence": 1.0, "source_class": "structural"},
        },
    }


def document_fingerprint(path: Path, ident: Dict[str, Any], text: str, tags: List[str], classification: Dict[str, Any]) -> Dict[str, Any]:
    norm = normalize_text(text)
    sections, merkle_root = build_sections(text)
    return asdict(DocumentFingerprint(
        identity={
            "file_sha256": ident.get("sha256", ""),
            "normalized_text_sha256": sha256_text(norm) if norm else "",
            "binary_size": ident.get("size_bytes", 0),
            "mime_type": path.suffix.lower().lstrip(".") or "unknown",
        },
        structural_tree={"merkle_root": merkle_root, "sections": [asdict(s) for s in sections]},
        semantic_profile={"tags": tags, "domain": classification.get("domain"), "content_type": classification.get("content_type"), "status": classification.get("status"), "topic_slug": classification.get("topic_slug"), "audience_scores": audience_scores(path)},
        provenance=provenance_for(path, classification),
        sparse_anchors=sparse_sentence_fingerprint(text),
        integrity={"fingerprint_version": "cluster-engine-v1", "generated_at": now_iso()},
    ))


def audience_scores(path: Path) -> Dict[str, float]:
    parts = {p.lower() for p in path.parts}
    return {layer: (1.0 if layer in parts else 0.0) for layer in READING_LAYERS}


def classify_path(path: Path, ident: Dict[str, Any], text: str) -> Dict[str, Any]:
    rec = config.FileRecord(path=str(path), name=path.name, extension=path.suffix.lower(), size_bytes=ident.get("size_bytes", 0), sha256=ident.get("sha256", ""), modified_at=ident.get("modified_at", ""), created_at=ident.get("created_at", ""))
    try:
        domain_classifier.classify(rec, text)
    except TypeError:
        result = domain_classifier.classify(str(path), text)  # type: ignore[arg-type]
        if isinstance(result, tuple):
            keys = ["domain", "content_type", "status", "date", "topic_slug"]
            return dict(zip(keys, result))
        if isinstance(result, dict):
            return result
    except Exception as exc:
        return {"domain": None, "content_type": None, "status": "unknown", "date": "", "topic_slug": path.stem, "error": str(exc)}
    rec.topic_slug = tagger.topic_slug(path.name)
    return {k: getattr(rec, k, None) for k in ("domain", "domain_label", "content_type", "status", "date", "topic_slug", "confidence")}


def iter_files(root: Path) -> Iterable[Path]:
    skip_dirs = set(config.IGNORE.get("skip_dirs", []))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                yield p


def discover(roots: Sequence[Path]) -> List[FileEntry]:
    entries: List[FileEntry] = []
    for root in roots:
        for path in iter_files(root):
            ident = fp_mod.fingerprint(str(path))
            text = text_extractor.extract_text(str(path), limit=20_000) or ""
            tags = tagger.extract_tags(path.name, text)
            classification = classify_path(path, ident, text)
            rel = str(path.relative_to(root)) if path.is_relative_to(root) else path.name
            folder_key = canonical_folder_key(path.parent.name)
            entries.append(FileEntry(str(path), str(root), rel, folder_key, ident, text[:20_000], tags, classification, sparse_sentence_fingerprint(text), document_fingerprint(path, ident, text, tags, classification), fp_mod.simhash(text) if text else ""))
    return entries


def canonical_folder_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return ALIASES.get(key, key)


def jaccard(a: Iterable[Any], b: Iterable[Any]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa or sb else 0.0


def target_groups(entries: List[FileEntry], target_root: Path) -> Dict[str, List[FileEntry]]:
    groups: Dict[str, List[FileEntry]] = defaultdict(list)
    for e in entries:
        p = Path(e.path)
        try:
            first = p.relative_to(target_root).parts[0]
        except Exception:
            first = e.folder_key
        groups[canonical_folder_key(first)].append(e)
    return groups


def source_groups(entries: List[FileEntry], source_roots: Sequence[Path], target_root: Path) -> Dict[str, List[FileEntry]]:
    groups: Dict[str, List[FileEntry]] = defaultdict(list)
    for e in entries:
        p = Path(e.path)
        if str(p).startswith(str(target_root)):
            continue
        try:
            rel = p.relative_to(Path(e.source_root))
            first = rel.parts[0] if len(rel.parts) > 1 else p.parent.name
        except Exception:
            first = p.parent.name
        groups[str(Path(e.source_root) / first)].append(e)
    return groups


def score_group(src: List[FileEntry], tgt: List[FileEntry], target_name: str) -> Dict[str, float]:
    src_folder = Path(src[0].path).parent.name if src else ""
    F = max(SequenceMatcher(None, canonical_folder_key(src_folder), target_name).ratio(), max((SequenceMatcher(None, canonical_folder_key(src_folder), canonical_folder_key(k)).ratio() for k in KNOWN_TARGET_FOLDERS), default=0.0) * 0.6)
    N = jaccard((Path(e.path).name.lower() for e in src), (Path(e.path).name.lower() for e in tgt))
    E = jaccard((Path(e.path).suffix.lower() for e in src), (Path(e.path).suffix.lower() for e in tgt))
    C = (jaccard((t for e in src for t in e.tags), (t for e in tgt for t in e.tags)) + jaccard((e.classification.get("domain") for e in src), (e.classification.get("domain") for e in tgt))) / 2
    H = jaccard((e.fingerprint.get("sha256") for e in src), (e.fingerprint.get("sha256") for e in tgt))
    src_m = [e.fingerprint.get("mtime", 0) for e in src]
    tgt_m = [e.fingerprint.get("mtime", 0) for e in tgt]
    T = 1.0 if src_m and tgt_m and abs((sum(src_m)/len(src_m)) - (sum(tgt_m)/len(tgt_m))) < 60*60*24*90 else 0.25
    P = 0.4 if any(w in e.path.lower() for e in src for w in PROVENANCE_PENALTY_WORDS) else 1.0
    Role = jaccard((e.classification.get("content_type") for e in src), (e.classification.get("content_type") for e in tgt))
    return {"F": F, "N": N, "E": E, "C": C, "H": H, "T": T, "P": P, "Role": Role}


def confidence(components: Dict[str, float]) -> int:
    max_score = sum(WEIGHTS.values())
    raw = sum(WEIGHTS[k] * components.get(k, 0.0) for k in WEIGHTS)
    return max(0, min(100, round(100 * raw / max_score)))


def detect_kills(src: List[FileEntry], tgt: List[FileEntry], rival_margin: float) -> List[str]:
    kills: List[str] = []
    by_name: Dict[str, set] = defaultdict(set)
    for e in src + tgt:
        by_name[Path(e.path).name.lower()].add(e.fingerprint.get("sha256"))
    if any(len(v) > 1 for v in by_name.values()):
        kills.append("same_filename_different_hash")
    tgt_by_name = {Path(e.path).name.lower(): e for e in tgt}
    for e in src:
        t = tgt_by_name.get(Path(e.path).name.lower())
        if t and t.fingerprint.get("mtime", 0) > e.fingerprint.get("mtime", 0) and t.fingerprint.get("sha256") != e.fingerprint.get("sha256"):
            kills.append("target_newer_than_incoming")
            break
    for e in src + tgt:
        parent = Path(e.path).parent
        if any((parent / marker).exists() for marker in PROTECTED_ROOT_MARKERS):
            kills.append("protected_program_root_detected")
            break
    if rival_margin < 0.12:
        kills.append("multiple_targets_low_rival_margin")
    if set(Path(e.path).name.lower() for e in src).issubset(set(Path(e.path).name.lower() for e in tgt)) and src:
        kills.append("incoming_folder_subset_of_target")
    if any(w in e.path.lower() for e in src for w in PROVENANCE_PENALTY_WORDS):
        kills.append("provenance_penalty_path_signal")
    src_layers = {part.lower() for e in src for part in Path(e.path).parts if part.lower() in READING_LAYERS}
    tgt_layers = {part.lower() for e in tgt for part in Path(e.path).parts if part.lower() in READING_LAYERS}
    if src_layers and tgt_layers and src_layers != tgt_layers:
        kills.append("reading_layer_conflict")
    stems: Dict[str, set] = defaultdict(set)
    for e in src + tgt:
        stems[Path(e.path).stem.replace(".canonical", "").lower()].add(Path(e.path).suffix.lower())
    if any(len(exts) > 1 for exts in stems.values()):
        kills.append("format_variants_detected")
    return sorted(set(kills))


def behavior_for(cluster_conf: int, safety: int) -> str:
    if cluster_conf >= 90 and safety >= 90:
        return "auto_execute_reversible"
    if cluster_conf >= 90 and safety >= 50:
        return "stage_require_batch_approval"
    if cluster_conf >= 90:
        return "link_logically_do_not_move"
    if cluster_conf >= 50:
        return "suggest_cluster_no_destructive_action"
    return "quarantine_logically"


def cluster_type(src: List[FileEntry], tgt: List[FileEntry], comps: Dict[str, float]) -> str:
    if comps.get("H", 0) > 0:
        return "IDENTITY"
    stems = defaultdict(set)
    for e in src + tgt:
        stems[Path(e.path).stem.replace(".canonical", "").lower()].add(Path(e.path).suffix.lower())
    if any(len(v) > 1 for v in stems.values()) or comps.get("C", 0) >= 0.45:
        return "FAMILY"
    return "PROJECT"


def build_clusters(entries: List[FileEntry], source_roots: Sequence[Path], target_root: Path) -> List[CandidateCluster]:
    tgroups = target_groups(entries, target_root)
    sgroups = source_groups(entries, source_roots, target_root)
    clusters: List[CandidateCluster] = []
    for sname, sfiles in sgroups.items():
        scored = []
        for tname, tfiles in tgroups.items():
            comps = score_group(sfiles, tfiles, tname)
            raw = sum(WEIGHTS[k] * comps[k] for k in WEIGHTS)
            scored.append((raw, tname, tfiles, comps))
        if not scored:
            continue
        scored.sort(reverse=True, key=lambda x: x[0])
        raw, tname, tfiles, comps = scored[0]
        margin = (raw - scored[1][0]) / max(1.0, raw) if len(scored) > 1 else 1.0
        cc = confidence(comps)
        kills = detect_kills(sfiles, tfiles, margin)
        safety = max(0, min(100, 92 - 18 * len([k for k in kills if k != "provenance_penalty_path_signal"])))
        if any(k in kills for k in ("same_filename_different_hash", "target_newer_than_incoming", "protected_program_root_detected", "reading_layer_conflict", "format_variants_detected")):
            safety = min(safety, 45)
        cid = "cluster-" + sha256_text(sname + "->" + tname)[:12]
        clusters.append(CandidateCluster(cid, sname, tname, [e.path for e in sfiles + tfiles], comps, raw, cc, safety, margin, cluster_type(sfiles, tfiles, comps), kills, behavior_for(cc, safety)))
    return clusters


def resolution_state(e: FileEntry, cluster: CandidateCluster, all_entries: List[FileEntry]) -> str:
    same_hash = [x for x in all_entries if x.fingerprint.get("sha256") == e.fingerprint.get("sha256")]
    if len(same_hash) > 1:
        return "IDENTICAL"
    if "same_filename_different_hash" in cluster.kill_conditions and any(Path(x.path).name.lower() == Path(e.path).name.lower() and x.path != e.path for x in all_entries):
        return "CONTENT_CONFLICT"
    low = e.path.lower()
    if any(x in low for x in ("signed", "legal", "original", "source")):
        return "PROTECTED_ORIGINAL"
    if e.fingerprint.get("size_bytes", 0) == 0 or (Path(e.path).suffix.lower() in {".pdf", ".docx"} and not e.text_preview):
        return "CORRUPT_CANDIDATE"
    if "format_variants_detected" in cluster.kill_conditions or any(layer in low for layer in READING_LAYERS):
        return "VALID_VARIANT"
    if Path(e.path).suffix.lower() in {".html", ".pdf", ".docx"}:
        return "DERIVED_OUTPUT"
    if cluster.cluster_confidence >= 70 and cluster.action_safety < 50:
        return "UNKNOWN_RELATION"
    return "UNIQUE_ADDITION"


def make_manifests(entries: List[FileEntry], clusters: List[CandidateCluster], outdir: Path, target_root: Path) -> Dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    by_path = {e.path: e for e in entries}
    discovery = {"type": "discovery_manifest", "generated_at": now_iso(), "files": [asdict(e) for e in entries]}
    resolutions = []
    actions = []
    rollback = {"type": "rollback_manifest", "generated_at": now_iso(), "operations": []}
    for c in clusters:
        for p in c.files:
            e = by_path[p]
            state = resolution_state(e, c, entries)
            resolutions.append({"path": p, "cluster_id": c.cluster_id, "state": state, "kill_conditions": c.kill_conditions})
        actions.append({"cluster_id": c.cluster_id, "source_folder": c.source_folder, "target_folder": str(target_root / c.target_folder), "operation": "logical_link" if c.action_safety < 90 or c.kill_conditions else "stage_move", "cluster_confidence": c.cluster_confidence, "action_safety": c.action_safety, "behavior": c.behavior, "kill_conditions": c.kill_conditions, "score_components": c.score_components, "rollback_required": True})
    paths = {
        "discovery": outdir / "discovery_manifest.json",
        "resolution": outdir / "resolution_manifest.json",
        "action": outdir / "action_manifest.json",
        "rollback": outdir / "rollback_manifest.json",
    }
    paths["discovery"].write_text(json.dumps(discovery, indent=2), encoding="utf-8")
    paths["resolution"].write_text(json.dumps({"type": "resolution_manifest", "generated_at": now_iso(), "resolutions": resolutions}, indent=2), encoding="utf-8")
    paths["action"].write_text(json.dumps({"type": "action_manifest", "generated_at": now_iso(), "actions": actions, "clusters": [asdict(c) for c in clusters]}, indent=2), encoding="utf-8")
    paths["rollback"].write_text(json.dumps(rollback, indent=2), encoding="utf-8")
    return paths


def cmd_scan(args: argparse.Namespace) -> int:
    roots = [Path(p).resolve() for p in args.source_dirs]
    target = Path(args.target).resolve()
    entries = discover(roots + [target])
    clusters = build_clusters(entries, roots, target)
    paths = make_manifests(entries, clusters, Path(args.output).resolve(), target)
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    if args.dry_run:
        print("dry-run: manifests generated; no filesystem changes performed")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.manifest_path).read_text(encoding="utf-8"))
    print(f"Manifest type: {data.get('type', 'unknown')}")
    if "files" in data:
        print(f"Files: {len(data['files'])}")
    if "actions" in data:
        counts = Counter(a.get("behavior") for a in data["actions"])
        print(f"Actions: {len(data['actions'])}  Behaviors: {dict(counts)}")
    if "resolutions" in data:
        counts = Counter(r.get("state") for r in data["resolutions"])
        print(f"Resolutions: {dict(counts)}")
    return 0


def execute_action_manifest(path: Path, approve: bool) -> int:
    if not approve:
        raise SystemExit("execute requires --approve")
    data = json.loads(path.read_text(encoding="utf-8"))
    # V1 intentionally only records that approved execution was reviewed.  Real
    # moves require concrete per-file destination ops generated in a future pass.
    executed = []
    for action in data.get("actions", []):
        if action.get("operation") == "stage_move" and not action.get("kill_conditions"):
            executed.append({**action, "executed": False, "reason": "v1_manifest_planner_only_no_per_file_destination"})
    print(json.dumps({"approved": True, "executed_operations": executed}, indent=2))
    return 0


def rollback_manifest(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    for op in reversed(data.get("operations", [])):
        if op.get("type") == "move" and Path(op["from"]).exists():
            shutil.move(op["from"], op["to"])
    print("rollback complete")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="David-OS cluster engine")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("source_dirs", nargs="+")
    scan.add_argument("--target", required=True)
    scan.add_argument("--dry-run", action="store_true")
    scan.add_argument("--output", default=str(config.REPORTS_DIR / "cluster_engine"))
    report = sub.add_parser("report")
    report.add_argument("manifest_path")
    execute = sub.add_parser("execute")
    execute.add_argument("action_manifest_path")
    execute.add_argument("--approve", action="store_true")
    rollback = sub.add_parser("rollback")
    rollback.add_argument("rollback_manifest_path")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return cmd_scan(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "execute":
        return execute_action_manifest(Path(args.action_manifest_path), args.approve)
    if args.command == "rollback":
        return rollback_manifest(Path(args.rollback_manifest_path))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
