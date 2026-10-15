#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional, Any

ENGINE_VERSION = "lossless-splitter-1.0.0"
FORMAT_VERSION = "LLS-1.0"

TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".json", ".jsonl", ".yaml", ".yml",
    ".html", ".htm", ".py", ".js", ".ts", ".tsx", ".jsx", ".css",
    ".csv", ".xml", ".toml", ".ini", ".cfg", ".lean",
}

H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
N_RE = re.compile(r"(?m)^\s*N\s*=\s*(.+?)\s*$")
V_RE = re.compile(r"(?m)^\s*V\s*=\s*(.+?)\s*$")
R_RE = re.compile(r"(?m)^\s*R\s*=\s*(.+?)\s*$")

@dataclass
class Identity:
    title: str
    namespace: Optional[str]
    variant: Optional[str]
    risk: Optional[str]
    base_slug: str

@dataclass
class ChunkRecord:
    index: int
    filename: str
    start_byte: int
    end_byte: int
    byte_count: int
    sha256: str
    heading: Optional[str]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)

def slugify(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^\w\-.]+", "_", value.strip(), flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_.")
    return (value or "UNTITLED")[:max_len]

def discover_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        yield source
        return
    for p in sorted(source.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS:
            yield p

SLUG_RE = re.compile(r"^[A-Za-z0-9][\w\-]*$")

def _header_zone(text: str) -> str:
    """First 25 lines, stopping at any ## heading or code fence."""
    lines = text.splitlines()[:25]
    zone = []
    for line in lines:
        if line.startswith("## ") or line.startswith("```"):
            break
        zone.append(line)
    return "\n".join(zone)

def parse_identity(path: Path, text: str) -> Identity:
    h1 = H1_RE.search(text)
    header = _header_zone(text)
    n_match = N_RE.search(header)
    namespace = None
    variant = None
    risk = None
    if n_match:
        val = n_match.group(1).strip()
        if SLUG_RE.match(val):
            namespace = val
    # V and R only count if N matched (identity is all-or-nothing)
    if namespace:
        v_match = V_RE.search(header)
        if v_match:
            val = v_match.group(1).strip()
            if SLUG_RE.match(val):
                variant = val
        r_match = R_RE.search(header)
        if r_match:
            val = r_match.group(1).strip()
            if SLUG_RE.match(val):
                risk = val
    title = h1.group(1).strip() if h1 else path.stem
    pieces = [namespace or title]
    if variant: pieces.append(variant)
    if risk: pieces.append(risk)
    base_slug = "__".join(slugify(x, 60) for x in pieces)
    return Identity(title, namespace, variant, risk, base_slug)

def char_to_byte_offsets(text: str) -> list[int]:
    offsets = [0]
    total = 0
    for ch in text:
        total += len(ch.encode("utf-8", errors="surrogateescape"))
        offsets.append(total)
    return offsets

def split_by_heading(raw: bytes, text: str, max_level: int):
    c2b = char_to_byte_offsets(text)
    heads = [(m.start(), m.group(2).strip()) for m in HEADING_RE.finditer(text)
             if len(m.group(1)) <= max_level]
    if not heads:
        return [(0, len(raw), None)]
    parts = []
    first = c2b[heads[0][0]]
    if first > 0:
        parts.append((0, first, "PREAMBLE"))
    for i, (cs, heading) in enumerate(heads):
        start = c2b[cs]
        end = c2b[heads[i+1][0]] if i + 1 < len(heads) else len(raw)
        if end > start:
            parts.append((start, end, heading))
    return parts

def split_by_size(raw: bytes, max_bytes: int):
    if len(raw) <= max_bytes:
        return [(0, len(raw), None)]
    parts, start = [], 0
    while start < len(raw):
        tentative = min(start + max_bytes, len(raw))
        if tentative < len(raw):
            floor = start + int(max_bytes * 0.85)
            nl = raw.rfind(b"\n", floor, tentative)
            end = nl + 1 if nl >= floor else tentative
        else:
            end = tentative
        if end <= start:
            end = min(start + max_bytes, len(raw))
        parts.append((start, end, None))
        start = end
    return parts

def split_smart(raw: bytes, text: str, max_level: int, max_bytes: int):
    out = []
    for start, end, heading in split_by_heading(raw, text, max_level):
        section = raw[start:end]
        if len(section) <= max_bytes:
            out.append((start, end, heading))
        else:
            for i, (ls, le, _) in enumerate(split_by_size(section, max_bytes), 1):
                label = f"{heading} [{i}]" if heading else None
                out.append((start + ls, start + le, label))
    return out

def make_name(identity: Identity, idx: int, total: int, heading: Optional[str], ext: str):
    h = slugify(heading, 55) if heading else "CHUNK"
    return f"{identity.base_slug}__P{idx:03d}-OF-{total:03d}__{h}{ext}"

def split_source(source_file: Path, corpus_root: Path, output_root: Path,
                 mode: str, heading_level: int, max_bytes: int):
    raw = source_file.read_bytes()
    text = raw.decode("utf-8", errors="surrogateescape")
    identity = parse_identity(source_file, text)
    rel = Path(source_file.name) if corpus_root.is_file() else source_file.relative_to(corpus_root)
    target = output_root / rel.parent / f"{source_file.stem}__SPLIT"
    target.mkdir(parents=True, exist_ok=True)

    if mode == "heading":
        slices = split_by_heading(raw, text, heading_level)
    elif mode == "size":
        slices = split_by_size(raw, max_bytes)
    else:
        slices = split_smart(raw, text, heading_level, max_bytes)

    records = []
    total = len(slices)
    for idx, (start, end, heading) in enumerate(slices, 1):
        chunk = raw[start:end]
        name = make_name(identity, idx, total, heading, source_file.suffix or ".txt")
        (target / name).write_bytes(chunk)
        records.append(ChunkRecord(idx, name, start, end, len(chunk), sha256_bytes(chunk), heading))

    rebuilt = b"".join((target / r.filename).read_bytes() for r in records)
    if rebuilt != raw:
        raise RuntimeError(f"Lossless reconstruction failed: {source_file}")

    manifest = {
        "format": FORMAT_VERSION,
        "engine": ENGINE_VERSION,
        "source": {
            "relative_path": rel.as_posix(),
            "filename": source_file.name,
            "sha256": sha256_bytes(raw),
            "byte_count": len(raw),
        },
        "identity": asdict(identity),
        "split": {
            "mode": mode,
            "heading_level": heading_level,
            "max_bytes": max_bytes,
            "chunk_count": total,
        },
        "chunks": [asdict(r) for r in records],
        "reconstruction": {
            "algorithm": "concatenate chunks in ascending index order",
            "expected_sha256": sha256_bytes(raw),
            "verified": True,
        },
    }
    manifest_name = f"{identity.base_slug}__split_manifest.json"
    (target / manifest_name).write_text(stable_json(manifest), encoding="utf-8")
    return {
        "source_path": rel.as_posix(),
        "source_sha256": sha256_bytes(raw),
        "chunk_count": total,
        "identity": asdict(identity),
        "source_manifest": (rel.parent / f"{source_file.stem}__SPLIT" / manifest_name).as_posix(),
    }

def build(source: Path, output: Path, mode: str, heading_level: int, max_bytes: int):
    source, output = source.resolve(), output.resolve()
    # Guard: output must not sit under source
    try:
        output.relative_to(source)
        raise RuntimeError(f"Output {output} is inside source {source} — would re-split splits on next run")
    except ValueError:
        pass  # not relative = not inside = good
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for file_path in discover_files(source):
        print(f"[SPLIT] {file_path}")
        rows.append(split_source(file_path, source, output, mode, heading_level, max_bytes))
    corpus_manifest = {
        "format": FORMAT_VERSION,
        "engine": ENGINE_VERSION,
        "source_root": str(source),
        "file_count": len(rows),
        "chunk_total": sum(r["chunk_count"] for r in rows),
        "sources": rows,
        "rules": {
            "naming_priority": ["N field", "first H1", "original filename"],
            "name_enrichment": ["V field", "R field", "part index", "heading"],
            "exact_reconstruction": True,
            "source_mutation": False,
        },
    }
    master = output / "corpus.split_manifest.json"
    master.write_text(stable_json(corpus_manifest), encoding="utf-8")
    print(f"Master manifest: {master}")
    return master

def main():
    p = argparse.ArgumentParser(description="Canonically name and losslessly split one file or many files.")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--mode", choices=("heading", "size", "smart"), default="smart")
    p.add_argument("--heading-level", type=int, choices=range(1,7), default=2)
    p.add_argument("--max-bytes", type=int, default=120000)
    a = p.parse_args()
    build(Path(a.source), Path(a.output), a.mode, a.heading_level, a.max_bytes)

if __name__ == "__main__":
    main()
