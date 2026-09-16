#!/usr/bin/env python3
"""Lossless corpus packer. L0 = source bytes. Compact index is derived (~21:1 target)."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from lossless_nse import document_payload, enclosure, formal_system_payload, infer_profile

FORMAT_VERSION = "LLP-1.0"
ENGINE_VERSION = "lossless-packer-1.0.0"
TARGET_RATIO = 21.0

TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".json", ".jsonl",
    ".yaml", ".yml", ".html", ".htm", ".py",
    ".js", ".ts", ".tsx", ".jsx", ".css", ".csv",
    ".xml", ".toml", ".ini", ".cfg", ".lean",
}
SKIP_DIRS = {".git", ".fis", "__pycache__", "node_modules", ".venv", "packets"}
SKIP_NAMES = {
    "thumbs.db", "desktop.ini", ".ds_store", "fis.html", "fis.lossless.json",
    "corpus.llmanifest.json", "corpus.split_manifest.json",
}
SKIP_SUFFIXES = (
    ".llp.zip", ".fisnote", ".fmeta", ".chi", ".fistag", ".fisdead",
    ".canon.sidecar.json",
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/\-]+)")
CODE_BLOCK_RE = re.compile(r"```([A-Za-z0-9_+\-]*)\n(.*?)```", re.DOTALL)
DISPLAY_MATH_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
VAR_LINE_RE = re.compile(r"^(G|M|E|S_eff|T|K|R|Q|F|C)\s*=\s*(.{12,})$", re.MULTILINE)

CLAIM_RE = re.compile(
    r"(?im)^\s*(?:"
    r"(?:claim|axiom|theorem|definition|prediction|hypothesis|primary claim|not primary claim)"
    r"\s*[:\-]\s*"
    r"|"
    r"\*\*(?:claim|axiom|theorem|definition|prediction|hypothesis)\*\*"
    r"\s*[:\-]?\s*"
    r")(.+)$"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def deterministic_id(relative_path: str, digest: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{relative_path}|{digest}"))


def skip_path(path: Path) -> bool:
    name = path.name.lower()
    if name in SKIP_NAMES or name.startswith(".fisnote.legacy."):
        return True
    return any(name.endswith(suf) for suf in SKIP_SUFFIXES)


def is_probably_text(path: Path, data: bytes) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    if b"\x00" in data[:8192]:
        return False
    try:
        data[:8192].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def extract_yaml_frontmatter(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def extract_structure(text: str) -> dict[str, Any]:
    headings = [
        {"level": len(m.group(1)), "title": m.group(2).strip(), "offset": m.start()}
        for m in HEADING_RE.finditer(text)
    ]
    code_blocks = [
        {"language": lang or None, "sha256": sha256_bytes(content.encode("utf-8")), "chars": len(content)}
        for lang, content in CODE_BLOCK_RE.findall(text)
    ]
    return {
        "yaml_frontmatter": extract_yaml_frontmatter(text),
        "headings": headings,
        "wikilinks": sorted(set(x.strip() for x in WIKILINK_RE.findall(text))),
        "markdown_link_count": len(MARKDOWN_LINK_RE.findall(text)),
        "uuids": sorted(set(UUID_RE.findall(text))),
        "tags": sorted(set(TAG_RE.findall(text))),
        "code_blocks": code_blocks,
        "display_equations": [eq.strip() for eq in DISPLAY_MATH_RE.findall(text)],
        "candidate_claims": [c.strip() for c in CLAIM_RE.findall(text) if c.strip()],
        "statistics": {
            "characters": len(text),
            "lines": text.count("\n") + 1,
            "words_approx": len(text.split()),
        },
    }


def _json_bytes(obj: Any) -> int:
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def compact_index(filename: str, text: str, extraction: dict[str, Any], source_bytes: int) -> dict[str, Any]:
    """Condensed operational index. Target ~21:1 vs source bytes. Never a substitute for L0."""
    budget = max(480, int(source_bytes / TARGET_RATIO))
    headings = [h["title"] for h in extraction.get("headings") or []]
    claims = list(extraction.get("candidate_claims") or [])
    equations = list(extraction.get("display_equations") or [])
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("chi_local") or s.startswith("chi_total"):
            if s not in equations:
                equations.append(s)
    variables = [{"id": i, "def": d.strip()[:48]} for i, d in VAR_LINE_RE.findall(text)]
    seen = set()
    uniq = []
    for var in variables:
        if var["id"] in seen:
            continue
        seen.add(var["id"])
        uniq.append(var)
    variables = uniq
    compact: dict[str, Any] = {
        "filename": filename,
        "profile": infer_profile(text, filename),
        "headings": [],
        "claims": [],
        "equations": [],
        "variables": [],
        "word_count": (extraction.get("statistics") or {}).get("words_approx"),
        "minimal": "",
    }
    for var in variables:
        compact = {**compact, "variables": compact["variables"] + [var]}
    for eq in equations:
        compact = {**compact, "equations": compact["equations"] + [eq]}
    for claim in claims:
        trial = {**compact, "claims": compact["claims"] + [claim]}
        if _json_bytes(trial) > budget:
            break
        compact = trial
    for title in headings:
        trial = {**compact, "headings": compact["headings"] + [title]}
        if _json_bytes(trial) > budget:
            break
        compact = trial
    ingest = ""
    if "IF ASKED WHAT IT IS:" in text:
        ingest = "formal coherence skeleton; prove only encoded theorem-cited claims; kill C/chi merge and S_prod as multiplier."
    thesis = compact["claims"][0] if compact["claims"] else (compact["headings"][1] if len(compact["headings"]) > 1 else compact["headings"][0] if compact["headings"] else filename)
    compact["minimal"] = ingest or thesis
    compact["source_bytes"] = source_bytes
    compact["compact_bytes"] = _json_bytes(compact)
    compact["compression_ratio"] = round(source_bytes / max(1, compact["compact_bytes"]), 2)
    return compact


@dataclass
class SourceRecord:
    packet_id: str
    relative_path: str
    source_sha256: str
    source_bytes: int
    mime_type: str | None
    is_text: bool
    packet_file: str
    compression_ratio: float | None
    payload_profile: str


def discover_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        yield source
        return
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if any(part.lower() in SKIP_DIRS or part.startswith(".fis") for part in path.parts):
            continue
        if skip_path(path):
            continue
        yield path


def create_packet(source_file: Path, corpus_root: Path, packets_dir: Path) -> SourceRecord:
    raw = source_file.read_bytes()
    digest = sha256_bytes(raw)
    relative_path = source_file.name if corpus_root.is_file() else source_file.relative_to(corpus_root).as_posix()
    packet_id = deterministic_id(relative_path, digest)
    text_file = is_probably_text(source_file, raw)
    extraction = None
    compact = None
    profile = "document"
    nse = None
    if text_file:
        text = raw.decode("utf-8", errors="replace")
        extraction = extract_structure(text)
        compact = compact_index(source_file.name, text, extraction, len(raw))
        profile = compact["profile"]
        payload = formal_system_payload(compact, text) if profile == "formal_system" else document_payload(compact, extraction)
        nse = enclosure(
            object_id=packet_id,
            source_sha256=digest,
            relative_path=relative_path,
            created_utc=utc_now(),
            payload_profile=profile,
            payload=payload,
            extraction_version=ENGINE_VERSION,
        )
    mime_type, _ = mimetypes.guess_type(source_file.name)
    packet_name = f"{packet_id}.llp.zip"
    packet_path = packets_dir / packet_name
    packet_metadata = {
        "format": FORMAT_VERSION,
        "engine": ENGINE_VERSION,
        "packet_id": packet_id,
        "created_utc": utc_now(),
        "source": {
            "relative_path": relative_path,
            "filename": source_file.name,
            "extension": source_file.suffix.lower(),
            "mime_type": mime_type,
            "byte_count": len(raw),
            "sha256": digest,
            "is_text": text_file,
        },
        "extraction": extraction,
        "compact": compact,
        "nse": nse,
        "integrity": {
            "canonical_source": True,
            "derived_extraction": extraction is not None,
            "reconstruction_rule": "original bytes are authoritative; compact/NSE may be regenerated",
        },
    }
    with zipfile.ZipFile(packet_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("packet.json", stable_json(packet_metadata))
        z.writestr(f"original/{relative_path}", raw)
        if compact is not None:
            z.writestr("compact.json", stable_json(compact))
    return SourceRecord(
        packet_id=packet_id,
        relative_path=relative_path,
        source_sha256=digest,
        source_bytes=len(raw),
        mime_type=mime_type,
        is_text=text_file,
        packet_file=f"packets/{packet_name}",
        compression_ratio=(compact or {}).get("compression_ratio") if compact else None,
        payload_profile=profile,
    )


def build_corpus(source: Path, output: Path, heuristic: bool = False) -> Path:
    source = source.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    packets_dir = output / "packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    discovered = list(discover_files(source))
    selected = discovered
    if heuristic:
        from fis_dup_heuristic import DUP_HARD, DUP_SOFT, jaccard, near_canon, word_set
        from collections import defaultdict
        sha_map: dict[str, list[Path]] = defaultdict(list)
        keep: set[Path] = set()
        bags = []
        for path in discovered:
            raw = path.read_bytes()
            digest = sha256_bytes(raw)
            sha_map[digest].append(path)
            bags.append((path, word_set(path)))
            if near_canon(path):
                keep.add(path)
        for group in sha_map.values():
            if len(group) > 1:
                keep.update(group)
        for i, (p1, s1) in enumerate(bags):
            if not s1:
                continue
            for p2, s2 in bags[i + 1 :]:
                if not s2 or p1.suffix.lower() != p2.suffix.lower():
                    continue
                if jaccard(s1, s2) >= DUP_SOFT:
                    keep.add(p1)
                    keep.add(p2)
        selected = [p for p in discovered if p in keep]
        print(f"Heuristic: {len(selected)}/{len(discovered)} files (dup >={int(DUP_SOFT*100)}%/{int(DUP_HARD*100)}% or near-canon)", flush=True)
    records: list[SourceRecord] = []
    for source_file in selected:
        print(f"[PACK] {source_file}")
        records.append(create_packet(source_file, source, packets_dir))
    digest_material = "\n".join(f"{r.relative_path}|{r.source_sha256}" for r in records)
    corpus_sha256 = sha256_bytes(digest_material.encode("utf-8"))
    manifest = {
        "format": FORMAT_VERSION,
        "engine": ENGINE_VERSION,
        "corpus": {
            "created_utc": utc_now(),
            "source_root": str(source),
            "file_count": len(records),
            "total_source_bytes": sum(r.source_bytes for r in records),
            "corpus_sha256": corpus_sha256,
            "target_compact_ratio": TARGET_RATIO,
        },
        "files": [asdict(r) for r in records],
        "lossless_contract": {
            "canonical_layer": "source bytes stored inside each packet",
            "derived_layer": "L1 extraction + compact index + NSE envelope",
            "semantic_summary": "NOT lossless; L0 remains attached",
            "verification": "SHA-256",
        },
        "future_layers": {
            "L0": "original bytes",
            "L1": "deterministic structural extraction",
            "L2": "compact operational index (~21:1 target)",
            "L3": "NSE payload by profile",
            "L4": "cross-document synthesis",
            "rule": "layers above L0 must not modify L0",
        },
    }
    manifest_path = output / "corpus.llmanifest.json"
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")
    print(f"Files packed: {len(records)}")
    print(f"Manifest:     {manifest_path}")
    print(f"Corpus hash:  {corpus_sha256}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an auditable lossless corpus.")
    parser.add_argument("source", help="Input file or directory")
    parser.add_argument("output", help="Output corpus directory")
    parser.add_argument("--heuristic", action="store_true",
                        help="Pack only exact/near duplicates (≥70%) and near-canon sidecar files")
    args = parser.parse_args()
    build_corpus(Path(args.source), Path(args.output), heuristic=args.heuristic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
