"""Score APOL defense formats on vault Markdown in shadow mode."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import heapq
import json
import math
from pathlib import Path
import re
import subprocess


FORMATS = (
    "01_MASTER_OBJECTION_DOSSIERS",
    "02_SEVEN_LAYER_DEFENSE_CARDS",
    "03_GRANULAR_OBJECTION_CARDS",
)
MAIN = Path("20_APOLOGETICS/01_APOLOGETICS_DEFENSE_FRAMEWORK")
SIGNALS = ("skeleton", "rare_words", "boilerplate", "meaning")
THRESHOLD = 0.60


@dataclass
class Document:
    path: Path
    digest: str
    body: str
    shape: tuple[str, ...]
    labels: set[str]
    words: Counter


def read(path):
    raw = path.read_bytes()
    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", raw.decode("utf-8-sig", errors="replace"), flags=re.S)
    shape, labels = [], set()
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        marker = re.match(r"^(#{1,6})\s+(.+)|^\*\*([^*]+)\*\*", line)
        if marker:
            kind = f"H{len(marker[1])}" if marker[1] else "B"
            label = " ".join(re.findall(r"[a-z]+", (marker[2] or marker[3]).lower()))
            if label:
                labels.add(label)
        elif line.startswith("|"):
            kind = "T"
        elif re.match(r"(?:[-*+]|\d+[.)])\s", line):
            kind = "L"
        elif line.startswith(">"):
            kind = "Q"
        else:
            kind = "P"
        if kind.startswith("H") or not shape or kind != shape[-1]:
            shape.append(kind)
    words = Counter(re.findall(r"[a-z]{4,}", body.lower()))
    return Document(path, hashlib.sha256(raw).hexdigest(), body, tuple(shape[:120]), labels, words)


def canon(doc):
    sidecar = doc.path.parent / "Sidecars_and_JSON" / (doc.path.name + ".canon.sidecar.json")
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8-sig"))
        lineage = data["lineage"]
        rulings = lineage["rulings"]
        if (data["sidecar_type"] == "canon_status" and rulings
                and lineage["source"]["source_sha256"].lower() == doc.digest):
            return {"standing": data["status"], "rulings": rulings, "sidecar": str(sidecar)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return {"standing": "unknown", "rulings": []}


def stable(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def run(root, model_path, control_count):
    format_paths = {}
    for base in (MAIN, Path("APOL_Apologetics_Framework"),
                 Path("ROAD_12_THE_FIVE_CONCESSIONS/01_ACADEMIC_ARM/APOL_Apologetics_Framework")):
        for family in FORMATS:
            for path in (root / base / family).rglob("*.md"):
                format_paths[path] = family
    # Use the same visible inventory ripgrep reports for the vault.
    inventory = subprocess.run(
        ["rg", "--files", "-0", "-g", "*.[mM][dD]", "-g", "!*.vial.md"],
        cwd=root, check=True, capture_output=True,
    ).stdout.decode("utf-8").split("\0")
    known = {str(path.relative_to(root)).replace("\\", "/").casefold() for path in format_paths}
    pool = [path.replace("\\", "/") for path in inventory if path]
    near = (path for path in pool if path.startswith("20_APOLOGETICS/") and path.casefold() not in known)
    far = (path for path in pool if not path.startswith("20_APOLOGETICS/") and path.casefold() not in known)
    near_count = control_count // 2
    controls = [root / path for path in heapq.nsmallest(near_count, near, key=stable)
                + heapq.nsmallest(control_count - near_count, far, key=stable)]
    print(f"Reading {len(format_paths)} format paths and {len(controls)} comparisons", flush=True)

    docs, aliases, groups, skipped = {}, defaultdict(list), defaultdict(list), []
    for path in sorted(format_paths, key=lambda p: (not p.is_relative_to(root / MAIN), str(p))) + controls:
        try:
            doc = read(path)
        except OSError as exc:
            skipped.append({"path": str(path), "reason": str(exc)})
            continue
        aliases[doc.digest].append(str(path))
        if doc.digest not in docs:
            docs[doc.digest] = doc
            groups[format_paths.get(path, "comparison")].append(doc.digest)
    seed_ids = []
    markers = {}
    for family in FORMATS:
        members = sorted(groups[family])
        if len(members) < 4:
            raise ValueError(f"{family} needs at least four distinct documents")
        seeds = members[:3]
        seed_ids.extend(seeds)
        shared = Counter(label for key in seeds for label in docs[key].labels)
        markers.update({key: {label for label, n in shared.items() if n >= 2} for key in seeds})

    # Fit rare words on exemplars and comparisons only, excluding held-out format documents.
    vocabulary = seed_ids + groups["comparison"]
    df = Counter(word for key in vocabulary for word in docs[key].words)
    fingerprints = {}
    for key in seed_ids:
        weights = {word: (1 + math.log(count)) * math.log((len(vocabulary) + 1) / (df[word] + 1))
                   for word, count in docs[key].words.items() if df[word] >= 2}
        fingerprints[key] = dict(sorted(weights.items(), key=lambda item: (-item[1], item[0]))[:25])

    meaning = None
    if model_path:
        print(f"Encoding {len(docs)} distinct documents locally", flush=True)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(str(model_path), local_files_only=True)
        vectors = model.encode([doc.body[:8000] for doc in docs.values()],
                               normalize_embeddings=True, batch_size=16, show_progress_bar=True)
        meaning = dict(zip(docs, vectors))

    rows = []
    for family, members in groups.items():
        for key in members:
            if key in seed_ids:
                continue
            doc = docs[key]
            matches = []
            for seed_key in seed_ids:
                seed = docs[seed_key]
                shared = sorted(markers[seed_key] & doc.labels)
                terms = {word: weight for word, weight in fingerprints[seed_key].items() if word in doc.words}
                shape = SequenceMatcher(None, seed.shape, doc.shape, autojunk=False).ratio()
                terms_score = sum(terms.values()) / (sum(fingerprints[seed_key].values()) or 1)
                boilerplate = len(shared) / len(markers[seed_key]) if markers[seed_key] else None
                semantic = max(0.0, min(1.0, float(meaning[key] @ meaning[seed_key]))) if meaning is not None else None
                scores = dict(zip(SIGNALS, (shape, terms_score, boilerplate, semantic)))
                weights = dict(zip(SIGNALS, (0.40, 0.10, 0.35, 0.15)))
                observed = [name for name in SIGNALS if scores[name] is not None]
                total = sum(weights[name] * scores[name] for name in observed) / sum(weights[name] for name in observed)
                evidence = {"skeleton": [list(doc.shape), list(seed.shape)],
                            "rare_words": sorted(terms), "boilerplate": shared,
                            "meaning": str(model_path) if model_path else "disabled"}
                matches.append((total, seed_key, scores, evidence))
            score, seed_key, scores, evidence = max(matches, key=lambda match: (match[0], match[1]))
            seed = docs[seed_key]
            rows.append({
                "sha256": key, "path": str(doc.path), "aliases": aliases[key],
                "reference_label": family, "proposal": "APOL" if score >= THRESHOLD else "unresolved",
                "score": round(score, 6), "scores": scores, "evidence": evidence,
                "canon_status": canon(doc), "reference_path": str(seed.path), "reference_sha256": seed_key,
                "preview": doc.body[:1400], "reference_preview": seed.body[:1400],
            })
    counts = {
        family: {"reviewed": len(group), "apol_proposed": sum(r["proposal"] == "APOL" for r in group)}
        for family in groups
        if (group := [r for r in rows if r["reference_label"] == family])
    }
    return {"schema": "david-os.apol-shadow.v1", "root": str(root), "threshold": THRESHOLD,
            "seeds": {key: str(docs[key].path) for key in seed_ids}, "counts": counts,
            "paths_read": sum(map(len, aliases.values())), "distinct_content": len(docs),
            "skipped": skipped, "rows": sorted(rows, key=lambda r: (abs(r["score"] - THRESHOLD), r["sha256"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", type=Path, help="Optional local MiniLM model directory")
    parser.add_argument("--controls", type=int, default=200)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("Write the shadow report outside the source vault")
    report = run(root, args.model, args.controls)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("counts", "paths_read", "distinct_content")}, indent=2))


if __name__ == "__main__":
    main()
