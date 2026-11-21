r"""deep_identify.py — Deep file-action: read content, classify documents, discover series.

Point it at a folder. It reads every qualifying file, classifies by document type,
discovers series/family relationships even when naming is wrong, and scores everything.

Read-only. Never moves, renames, or deletes anything.

Usage:
    python deep_identify.py scan TARGET_FOLDER [--output report_dir] [--max-files 500]
    python deep_identify.py scan TARGET_FOLDER --series-only
    python deep_identify.py report REPORT_DIR

Output:
    report_dir/deep_identify.json     full structured report
    report_dir/file_cards.csv         one row per file with scores
    report_dir/families.csv           discovered series/families
    report_dir/orphans.csv            files that don't belong to any family
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".lake", ".obsidian", ".smart-env", ".claudian", ".trash", ".git",
    "node_modules", "__pycache__", ".venv", "venv", "site-packages",
    ".cache", ".next", "dist-packages", "$recycle.bin", "#recycle",
    "#snapshot", "system volume information", "windows",
    "program files", "program files (x86)", "programdata", "appdata",
    "@eadir",
}

# Level 0: container type markers
CONTAINER_MARKERS = {
    ".obsidian": "obsidian_vault",
    ".git": "git_repo",
    "package.json": "js_project",
    "pyproject.toml": "python_project",
    "requirements.txt": "python_project",
    "cargo.toml": "rust_project",
    "go.mod": "go_project",
    "lakefile.lean": "lean_project",
    "lakefile.toml": "lean_project",
    "docker-compose.yml": "docker_stack",
    "docker-compose.yaml": "docker_stack",
}
PROJECT_MARKERS = {"git_repo", "js_project", "python_project", "rust_project",
                   "go_project", "lean_project", "docker_stack"}

# Level 1: file kind by extension
KIND_EXT = {
    "code": ".py .js .ts .tsx .jsx .mjs .cjs .java .c .cpp .h .cs .go .rs .rb .php .ps1 .bat .cmd .sh .ahk .lean .sql .vue .svelte",
    "document": ".md .txt .pdf .doc .docx .rtf .odt .epub .tex .html .htm",
    "picture": ".png .jpg .jpeg .gif .webp .bmp .tif .tiff .svg .heic .ico .psd",
    "video": ".mp4 .mkv .mov .avi .webm .wmv .flv .m4v",
    "audio": ".mp3 .wav .flac .m4a .aac .ogg .opus .wma",
    "data": ".csv .xlsx .xls .json .jsonl .yaml .yml .xml .sqlite .sqlite3 .db .parquet .tsv",
    "archive": ".zip .7z .rar .tar .gz .tgz .bz2 .iso",
    "config": ".env .ini .toml .cfg .conf .lock",
    "sidecar": ".chi .fmeta .srt .vtt",
}
EXT_KIND = {ext: kind for kind, exts in KIND_EXT.items() for ext in exts.split()}

# Level 2: domain keywords
DOMAIN_WORDS = {
    "theophysics": "axiom theophysics logos coherence chi master equation canon lean grace trinity faith physics derivation law gospel bible scripture resurrection atonement entropy",
    "website": "site website html css public dist index assets page template layout nav header footer",
    "business": "invoice quote estimate fence fencing customer receipt tax payroll contract",
    "ai_chats": "chatgpt claude gemini kimi codex conversation transcript export prompt chat deepseek gpt",
    "media": "video audio tts podcast youtube mp4 thumbnail render obs recording",
}
DOMAIN_TOKENS = {d: set(w.split()) for d, w in DOMAIN_WORDS.items()}

# Level 3: document type patterns
DOC_TYPE_SIGNALS = {
    "paper": {
        "markers": ["abstract", "introduction", "conclusion", "references", "we show", "we prove", "we demonstrate", "this paper"],
        "min_length": 500,
        "has_sections": True,
    },
    "note": {
        "markers": ["todo", "note to self", "scratch", "quick thought", "reminder"],
        "min_length": 0,
        "has_sections": False,
    },
    "guide": {
        "markers": ["step 1", "how to", "instructions", "guide", "tutorial", "getting started", "setup"],
        "min_length": 200,
        "has_sections": True,
    },
    "identity_card": {
        "markers": ["---\n", "title:", "date:", "author:", "status:", "series:"],
        "min_length": 0,
        "has_sections": False,
    },
    "template": {
        "markers": ["{{", "{%", "<!-- template", "placeholder", "[REPLACE", "[INSERT"],
        "min_length": 0,
        "has_sections": False,
    },
    "data_artifact": {
        "markers": [],  # detected by extension, not content
        "min_length": 0,
        "has_sections": False,
    },
}

# Level 4: series detection
SERIES_NUMBER_RE = re.compile(
    r"(?:^|[_\-\s])(?:part|chapter|ch|paper|p|no|num|road|law|ms|me|sp|ss|der|god.?is|axiom)[_\-\s]*(\d{1,3})(?:[_\-\s.]|$)",
    re.IGNORECASE,
)
POSITION_RE = re.compile(r"(?:^|[_\-\s])(\d{1,3})[_\-\s]", re.IGNORECASE)
ROMAN_RE = re.compile(r"(?:^|[_\-\s])(I{1,3}|IV|VI{0,3}|IX|X{0,3})(?:[_\-\s.]|$)")

# How many bytes of content to read for classification
CONTENT_SAMPLE_BYTES = 8192

# Binary document formats: not decodable as text; flagged until a format-aware extractor is wired in
BINARY_DOC_EXT = {".pdf", ".doc", ".docx", ".odt", ".epub", ".rtf"}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class FileCard:
    """One card per file — answers the rule_brick questions with scores."""
    path: str
    name: str
    extension: str
    size_bytes: int
    modified_at: str
    sha256: str = ""

    # Level 0: safety
    container_type: str = "unknown"       # obsidian_vault, git_repo, research, media, etc.
    is_protected: bool = False            # in a project root or marked don't-touch
    can_move: bool = True
    can_rename: bool = True

    # Level 1: kind
    file_kind: str = "unknown"            # code, document, picture, video, audio, data, etc.

    # Level 2: domain
    domain: str = "unknown"               # theophysics, website, business, etc.
    domain_confidence: float = 0.0

    # Level 3: document type
    doc_type: str = "unknown"             # paper, note, guide, template, identity_card, data_artifact
    doc_type_confidence: float = 0.0
    content_length: int = 0
    has_yaml_frontmatter: bool = False
    has_sections: bool = False
    section_count: int = 0

    # Level 4: series/family
    family_id: str = ""                   # assigned during clustering
    family_name: str = ""
    position_in_family: int = -1          # -1 = unknown
    position_source: str = ""             # "filename_number", "content_reference", "vocabulary", ""

    # Scoring
    identity_confidence: float = 0.0      # overall: how sure are we about what this is
    relationship_strength: float = 0.0    # how strongly it belongs to its family
    orphan_probability: float = 0.0       # inverse of relationship_strength

    # Evidence
    title_tokens: list = field(default_factory=list)
    content_tokens: list = field(default_factory=list)  # top N distinctive words
    references_to: list = field(default_factory=list)    # filenames mentioned in content
    referenced_by: list = field(default_factory=list)    # other files that mention this one
    ambiguous_refs: list = field(default_factory=list)   # names that matched more than one file
    extraction_status: str = ""                          # read / unsupported_binary_format / skipped_too_large / empty_or_unreadable


@dataclass
class Family:
    """A discovered group of related files."""
    family_id: str
    family_name: str
    members: list = field(default_factory=list)       # list of paths
    member_count: int = 0
    evidence: list = field(default_factory=list)       # what connected them
    confidence: float = 0.0
    is_series: bool = False                            # ordered sequence vs unordered group
    completeness: float = 0.0                          # if series: what fraction of positions filled
    gaps: list = field(default_factory=list)            # missing position numbers
    domain: str = "unknown"
    competing_versions: dict = field(default_factory=dict)  # position -> [paths] when 2+ files claim one slot
    score_semantics: str = "heuristic_uncalibrated"         # not a probability until measured on labeled data



# ── Helpers ──────────────────────────────────────────────────────────────────

def _sha256(path: Path, max_bytes: int = 512 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return "TOO_LARGE"
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return "UNREADABLE"


def _read_sample(path: Path, max_bytes: int = CONTENT_SAMPLE_BYTES) -> str:
    """Read the first N bytes as text. Returns empty string on binary/error."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)
    except (OSError, PermissionError, UnicodeDecodeError):
        return ""


def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer — lowercase, 3+ char words."""
    return [w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)]


# ── Level 0: Container type detection ────────────────────────────────────────

def detect_container(folder: Path) -> tuple[str, bool]:
    """What kind of container is this folder? Returns (type, is_protected)."""
    markers_found = set()
    try:
        entries = {e.name.lower(): e.name for e in folder.iterdir()}
    except (OSError, PermissionError):
        return "unknown", False

    for marker_name, marker_type in CONTAINER_MARKERS.items():
        if marker_name.lower() in entries:
            markers_found.add(marker_type)

    is_project = bool(markers_found & PROJECT_MARKERS)

    if "obsidian_vault" in markers_found:
        return "obsidian_vault", True  # protected: moving breaks wikilinks
    if is_project:
        return sorted(markers_found & PROJECT_MARKERS)[0], True
    # Check content mix to guess
    exts = Counter()
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        for f in files:
            exts[Path(f).suffix.lower()] += 1
        if sum(exts.values()) > 200:
            break  # sample enough
    if not exts:
        return "empty", False
    doc_count = sum(exts.get(e, 0) for e in ".md .txt .html .htm .pdf .docx".split())
    code_count = sum(exts.get(e, 0) for e in ".py .js .ts .rs .go .java .lean".split())
    media_count = sum(exts.get(e, 0) for e in ".png .jpg .mp4 .mp3 .wav".split())
    total = sum(exts.values())
    if doc_count / total > 0.6:
        return "research_writing", False
    if code_count / total > 0.5:
        return "code_folder", False
    if media_count / total > 0.5:
        return "media_folder", False
    return "mixed", False


# ── Level 2: Domain detection ────────────────────────────────────────────────

def detect_domain(tokens: list[str]) -> tuple[str, float]:
    """Score content tokens against domain vocabularies."""
    if not tokens:
        return "unknown", 0.0
    token_set = set(tokens)
    scores = {}
    for domain, vocab in DOMAIN_TOKENS.items():
        overlap = token_set & vocab
        scores[domain] = len(overlap) / max(len(vocab), 1)
    if not scores:
        return "unknown", 0.0
    best = max(scores, key=scores.get)
    conf = scores[best]
    if conf < 0.05:
        return "unknown", 0.0
    # Normalize: how much better is the winner than second place?
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) > 1 and sorted_scores[1] > 0:
        margin = (sorted_scores[0] - sorted_scores[1]) / sorted_scores[0]
    else:
        margin = 1.0
    return best, round(min(conf * 3, 1.0) * (0.5 + 0.5 * margin), 4)


# ── Level 3: Document type classification ────────────────────────────────────

def detect_doc_type(text: str, extension: str, file_kind: str) -> tuple[str, float]:
    """Classify document type from content sample."""
    if file_kind in ("picture", "video", "audio", "archive"):
        return "media", 0.9
    if file_kind == "data":
        return "data_artifact", 0.9
    if file_kind == "config":
        return "config", 0.9
    if file_kind == "code":
        return "code", 0.9
    if file_kind == "sidecar":
        return "sidecar", 0.9

    if not text:
        return "unknown", 0.0

    # YAML frontmatter is a header on a document, not the document's type. Judge the body.
    # Only a file that is (nearly) all frontmatter is an identity card.
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end == -1:
            return "identity_card", 0.6          # frontmatter runs past the whole sample
        body = text[end + 4:]
        if len(body.strip()) < 400:
            return "identity_card", 0.8
        text = body

    text_lower = text.lower()
    scores = {}
    for dtype, signals in DOC_TYPE_SIGNALS.items():
        if dtype == "identity_card":
            continue
        hits = sum(1 for m in signals["markers"] if m.lower() in text_lower)
        if hits == 0:
            continue  # no marker evidence -> this label is not a candidate (abstain, don't guess)
        total_markers = len(signals["markers"]) or 1
        marker_score = hits / total_markers

        length_ok = len(text) >= signals["min_length"]
        # Check for section headers (markdown ## or HTML <h2>)
        section_count = len(re.findall(r"^#{1,3}\s+\S", text, re.MULTILINE))
        section_count += len(re.findall(r"<h[1-3]", text_lower))
        has_sections = section_count >= 2

        section_match = 1.0
        if signals["has_sections"] and not has_sections:
            section_match = 0.3
        elif not signals["has_sections"] and has_sections:
            section_match = 0.7

        scores[dtype] = marker_score * 0.5 + (1.0 if length_ok else 0.3) * 0.25 + section_match * 0.25

    if not scores:
        return "unknown", 0.0
    best = max(scores, key=scores.get)
    conf = scores[best]
    if conf < 0.2:
        return "unknown", round(conf, 4)
    return best, round(min(conf, 1.0), 4)


# ── Level 4: Series / family discovery ───────────────────────────────────────

def extract_position(filename: str) -> tuple[int, str]:
    """Try to pull a series position number from a filename."""
    m = SERIES_NUMBER_RE.search(filename)
    if m:
        return int(m.group(1)), "filename_prefix"
    m = POSITION_RE.search(filename)
    if m:
        return int(m.group(1)), "filename_number"
    m = ROMAN_RE.search(filename)
    if m:
        roman = m.group(1).upper()
        roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
                     "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
        return roman_map.get(roman, -1), "roman_numeral"
    return -1, ""


DOC_CODE_RE = re.compile(r"^([A-Za-z]{1,4}-\d{2,4})([A-Za-z]?)(?=[_\-\s.]|$)")


def doc_code(filename: str) -> str:
    """Leading document code like FT-003 / DT-001 / O-09. A trailing letter (FP-002A) is a companion
    of the base code, so the base is returned. Files sharing a code are one document's artifacts."""
    m = DOC_CODE_RE.match(Path(filename).stem)
    return m.group(1).upper() if m else ""


def extract_title_root(filename: str) -> str:
    """Strip numbers, extensions, common suffixes to get the title root."""
    stem = Path(filename).stem
    stem = re.sub(r"^[A-Za-z]{1,4}-\d{2,4}[A-Za-z]?[_\-\s.]+", "", stem)          # leading document code
    stem = re.sub(r"(?i)\.(canonical|final|draft|scored|v\d+)$", "", stem)      # dotted status suffix
    stem = re.sub(r"[_\-]+", " ", stem)
    # Remove position indicators
    root = re.sub(r"[_\-\s]*\d{1,3}[_\-\s]*", " ", stem)
    # Remove common suffixes (whole words only — "newton" must not lose its "new")
    root = re.sub(r"(?i)\b(final|draft|v\d+|copy|backup|old|new|revised)\b", " ", root)
    # Collapse whitespace
    root = re.sub(r"\s+", " ", root).strip().lower()
    return root


def find_cross_references(text: str, name_index: dict, self_path: str) -> tuple[list, list]:
    """Resolve wikilinks, markdown/HTML links and bare filename mentions to real paths.

    Returns (resolved_paths, ambiguous_names). Self-links are dropped. A name that
    matches more than one file is reported as ambiguous, never guessed.
    """
    names: set[str] = set()
    for m in re.finditer(r"\[\[([^\]|#]+)", text):                      # [[Target|alias]]
        names.add(Path(m.group(1).strip()).stem.lower())
    for m in re.finditer(r"\]\(([^)#\s]+)\)", text):                    # [text](file.md)
        names.add(Path(m.group(1).strip()).stem.lower())
    for m in re.finditer(r"href=[\"']([^\"'#]+)[\"']", text, re.I):      # href="file.html"
        names.add(Path(m.group(1).strip()).stem.lower())
    # Bare mentions: pull filename-shaped tokens out of the text once and look them up (cost ~ text size,
    # not text size x number of files in the tree)
    for tok in set(re.findall(r"[a-z0-9][a-z0-9_\-\.]{7,}", text.lower())):
        tok = tok.rstrip(".")
        if not re.search(r"[_\-\d]|\.[a-z]{2,5}$", tok):
            continue  # an ordinary word ("introduction") is not a filename mention
        if tok in name_index:
            names.add(tok)
        else:
            stem = tok.rsplit(".", 1)[0]
            if len(stem) >= 8 and stem in name_index:
                names.add(stem)
    resolved, ambiguous = [], []
    self_resolved = str(Path(self_path))
    for name in sorted(names):
        targets = [p for p in name_index.get(name, []) if p != self_resolved]
        if len(targets) == 1:
            resolved.append(targets[0])
        elif len(targets) > 1:
            ambiguous.append(name)
    return resolved, ambiguous


def _cluster_into_families_v0(cards: list[FileCard]) -> list[Family]:
    """RETIRED 2026-11-12 (crew BREAK): only title roots could create a family. Kept for reference."""
    # Only cluster documents (not code, media, config, etc.)
    doc_cards = [c for c in cards if c.file_kind == "document" and c.doc_type in ("paper", "guide", "note", "identity_card", "unknown")]

    if not doc_cards:
        return []

    # Signal 1: Title root grouping
    root_groups: dict[str, list[FileCard]] = defaultdict(list)
    for card in doc_cards:
        root = extract_title_root(card.name)
        if root and len(root) > 3:
            root_groups[root].append(card)

    # Signal 2: Cross-reference grouping
    ref_groups: dict[str, set[str]] = defaultdict(set)
    for card in doc_cards:
        for ref in card.references_to:
            ref_groups[ref].add(card.path)
        for ref in card.referenced_by:
            ref_groups[ref].add(card.path)

    # Signal 3: Vocabulary similarity (cosine of top-50 tokens)
    def vocab_similarity(a: FileCard, b: FileCard) -> float:
        sa = set(a.content_tokens[:50])
        sb = set(b.content_tokens[:50])
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / math.sqrt(len(sa) * len(sb))

    # Build families from title roots (primary signal)
    families = []
    used = set()
    for root, members in sorted(root_groups.items(), key=lambda x: -len(x[1])):
        if len(members) < 2:
            continue
        paths = [c.path for c in members]
        if any(p in used for p in paths):
            continue

        # Check if this is an ordered series
        positions = {}
        for card in members:
            pos, source = extract_position(card.name)
            if pos >= 0:
                positions[card.path] = (pos, source)

        is_series = len(positions) >= 2
        if is_series:
            pos_nums = sorted(p[0] for p in positions.values())
            expected = list(range(min(pos_nums), max(pos_nums) + 1))
            gaps = [n for n in expected if n not in pos_nums]
            completeness = len(pos_nums) / len(expected) if expected else 0.0
        else:
            gaps = []
            completeness = 0.0

        # Score the family
        evidence = ["title_root_match"]
        conf = 0.6  # base from title root

        # Boost if cross-references exist between members
        member_names = {Path(c.path).stem.lower() for c in members}
        cross_ref_count = sum(
            1 for c in members
            for ref in c.references_to
            if Path(ref).stem.lower() in member_names
        )
        if cross_ref_count > 0:
            conf += 0.15
            evidence.append(f"cross_references:{cross_ref_count}")

        # Boost if vocabulary is similar
        if len(members) >= 2:
            sim_scores = []
            for i in range(min(len(members), 5)):
                for j in range(i + 1, min(len(members), 5)):
                    sim_scores.append(vocab_similarity(members[i], members[j]))
            avg_sim = sum(sim_scores) / len(sim_scores) if sim_scores else 0.0
            if avg_sim > 0.3:
                conf += 0.15
                evidence.append(f"vocabulary_similarity:{avg_sim:.3f}")

        if is_series:
            conf += 0.1
            evidence.append(f"sequential_numbering:positions={sorted(p[0] for p in positions.values())}")

        conf = min(conf, 1.0)

        fam = Family(
            family_id=f"FAM-{len(families)+1:03d}",
            family_name=root.replace(" ", "_"),
            members=paths,
            member_count=len(members),
            evidence=evidence,
            confidence=round(conf, 4),
            is_series=is_series,
            completeness=round(completeness, 4),
            gaps=gaps,
            domain=Counter(c.domain for c in members).most_common(1)[0][0] if members else "unknown",
        )
        families.append(fam)

        # Assign back to cards
        for card in members:
            card.family_id = fam.family_id
            card.family_name = fam.family_name
            card.relationship_strength = conf
            card.orphan_probability = round(1.0 - conf, 4)
            if card.path in positions:
                card.position_in_family = positions[card.path][0]
                card.position_source = positions[card.path][1]

        used.update(paths)

    # Mark orphans
    for card in doc_cards:
        if card.path not in used:
            card.orphan_probability = 0.8
            card.relationship_strength = 0.1

    return families


# ── Main scan pipeline ───────────────────────────────────────────────────────

def scan_folder(target: Path, max_files: int = 2000) -> tuple[list[FileCard], list[Family], dict]:
    """Full deep-identify scan. Read-only. Returns (cards, families, stats)."""
    target = target.resolve()
    stats = {
        "target": str(target),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "files_scanned": 0,
        "files_skipped": 0,
        "errors": [],
        "container_type": "unknown",
        "container_protected": False,
        "families_found": 0,
        "orphans": 0,
        "domain_distribution": {},
        "doc_type_distribution": {},
        "kind_distribution": {},
        "avg_identity_confidence": 0.0,
    }

    # Detect container
    ctype, cprot = detect_container(target)
    stats["container_type"] = ctype
    stats["container_protected"] = cprot

    # Crawl
    cards: list[FileCard] = []
    all_filenames: set[str] = set()
    name_index: dict[str, list[str]] = defaultdict(list)   # stem -> every path with that stem
    dir_info: dict[str, tuple[str, bool]] = {}              # folder -> (container_type, protected)

    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS)
        rp = Path(root)
        # Protection is per folder: a project marker here, or in any ancestor up to the scan root, protects it.
        names_here = {n.lower() for n in list(files) + [d for d in os.listdir(root) if (rp / d).is_dir()]} if rp.exists() else set()
        marks = {CONTAINER_MARKERS[m] for m in CONTAINER_MARKERS if m.lower() in names_here}
        own = "obsidian_vault" if "obsidian_vault" in marks else (sorted(marks & PROJECT_MARKERS)[0] if marks & PROJECT_MARKERS else "")
        parent_info = dir_info.get(str(rp.parent)) if rp != target else (ctype, cprot)
        if own:
            dir_info[str(rp)] = (own, True)
        else:
            dir_info[str(rp)] = parent_info or (ctype, cprot)
        for fname in files:
            all_filenames.add(fname)
            name_index[Path(fname).stem.lower()].append(str(rp / fname))
    stats["files_seen"] = sum(len(v) for v in name_index.values())

    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS)
        files = sorted(files)
        here_type, here_prot = dir_info.get(str(Path(root)), (ctype, cprot))
        for fname in files:
            if len(cards) >= max_files:
                stats["files_skipped"] += 1
                continue

            fp = Path(root) / fname
            ext = fp.suffix.lower()
            file_kind = EXT_KIND.get(ext, "unknown")

            try:
                st = fp.stat()
            except (OSError, PermissionError) as e:
                stats["errors"].append(f"{fp}: {e}")
                continue

            card = FileCard(
                path=str(fp),
                name=fname,
                extension=ext,
                size_bytes=st.st_size,
                modified_at=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                container_type=here_type,
                is_protected=here_prot,
                can_move=not here_prot,
                can_rename=not here_prot,
                file_kind=file_kind,
            )

            # Content reading for documents (binary formats get an honest status, not UTF-8 garbage)
            if ext in BINARY_DOC_EXT:
                card.extraction_status = "unsupported_binary_format"
            elif file_kind == "document" and st.st_size >= 5 * 1024 * 1024:
                card.extraction_status = "skipped_too_large"
            if file_kind == "document" and ext not in BINARY_DOC_EXT and st.st_size < 5 * 1024 * 1024:
                text = _read_sample(fp)
                card.extraction_status = "read" if text else "empty_or_unreadable"
                if text:
                    card.content_length = len(text)
                    card.has_yaml_frontmatter = text.startswith("---\n")
                    tokens = _tokenize(text)
                    card.content_tokens = [t for t, _ in Counter(t for t in tokens if t not in STOPWORDS).most_common(60)]
                    card.title_tokens = _tokenize(fp.stem)

                    # Level 2: domain
                    card.domain, card.domain_confidence = detect_domain(tokens)

                    # Level 3: doc type
                    card.doc_type, card.doc_type_confidence = detect_doc_type(text, ext, file_kind)
                    card.section_count = len(re.findall(r"^#{1,3}\s+\S", text, re.MULTILINE))
                    card.has_sections = card.section_count >= 2

                    # Cross-references
                    card.references_to, card.ambiguous_refs = find_cross_references(text, name_index, str(fp))
            else:
                card.domain, card.domain_confidence = detect_domain(_tokenize(fp.stem))
                card.doc_type, card.doc_type_confidence = detect_doc_type("", ext, file_kind)

            # Position extraction
            pos, src = extract_position(fname)
            if pos >= 0:
                card.position_in_family = pos
                card.position_source = src

            # Hash only what is cheap to hash; big media is identified by size/date until a dedupe pass asks
            if st.st_size <= 25 * 1024 * 1024:
                card.sha256 = _sha256(fp)
            else:
                card.sha256 = "NOT_HASHED_LARGE"
            if stats["files_scanned"] and stats["files_scanned"] % 500 == 0:
                print(f"  ... {stats['files_scanned']} files", flush=True)

            # Overall identity confidence
            conf_signals = [
                card.domain_confidence,
                card.doc_type_confidence,
                1.0 if card.file_kind != "unknown" else 0.0,
                0.8 if card.has_yaml_frontmatter else 0.0,
                0.5 if card.section_count > 0 else 0.0,
            ]
            card.identity_confidence = round(sum(conf_signals) / len(conf_signals), 4)

            cards.append(card)
            stats["files_scanned"] += 1

    # Reverse index: exact resolved paths only (no substring guessing)
    path_to_card = {c.path: c for c in cards}
    for card in cards:
        for ref in card.references_to:
            other = path_to_card.get(ref)
            if other is not None and card.path not in other.referenced_by:
                other.referenced_by.append(card.path)

    # Cluster into families
    families, weak = cluster_into_families(cards)
    stats["families_found"] = len(families)
    stats["weak_candidate_pairs"] = len(weak)
    stats["weak_candidates"] = weak[:500]
    stats["vocabulary_pairing"] = "skipped_over_limit" if sum(1 for c in cards if c.file_kind == "document") > VOCAB_PAIR_LIMIT else "all_pairs"
    stats["orphans"] = sum(1 for c in cards if c.file_kind == "document" and c.orphan_probability > 0.5)

    # Distribution stats
    stats["domain_distribution"] = dict(Counter(c.domain for c in cards).most_common())
    stats["doc_type_distribution"] = dict(Counter(c.doc_type for c in cards).most_common())
    stats["kind_distribution"] = dict(Counter(c.file_kind for c in cards).most_common())
    stats["avg_identity_confidence"] = round(
        sum(c.identity_confidence for c in cards) / max(len(cards), 1), 4
    )
    stats["extraction_status"] = dict(Counter(c.extraction_status for c in cards if c.file_kind == "document").most_common())
    stats["coverage"] = round(stats["files_scanned"] / max(stats.get("files_seen", 0), 1), 4)
    stats["score_semantics"] = "heuristic_uncalibrated"
    stats["completed_at"] = datetime.now(timezone.utc).isoformat()

    return cards, families, stats


# ── Level 4 (v1): evidence-graph family discovery ────────────────────────────
# Any of four signals can NOMINATE a pair. A pair becomes a family edge only if
#   - one file explicitly links to the other (resolved path), or
#   - two independent signals agree (e.g. title root + numbering, title root + vocabulary).
# A single weak signal is kept as a "weak candidate" for review, never merged.

STOPWORDS = set("""the and for that this with from are was were been have has had not but you your our their
they them his her its which what when where who will would can could should into about than then there these
those also more most such only other some any all one two each over under very just like make made does did
being been here how why our out use used using upon via per may might must shall""".split())

VOCAB_NOMINATE = 0.55       # overlap of distinctive vocabulary needed to nominate a pair
VOCAB_PAIR_LIMIT = 1500     # above this many documents, skip all-pairs vocabulary (reported in stats)
EVIDENCE_WEIGHT = {"link": 0.50, "doc_code": 0.50, "title_root": 0.35, "numbering": 0.25, "vocabulary": 0.35}


def cluster_into_families(cards: list[FileCard]) -> tuple[list[Family], list[dict]]:
    """Returns (families, weak_candidate_pairs)."""
    doc_cards = sorted(
        (c for c in cards if c.file_kind == "document"
         and c.doc_type in ("paper", "guide", "note", "identity_card", "unknown")),
        key=lambda c: c.path.casefold())
    if not doc_cards:
        return [], []
    by_path = {c.path: c for c in doc_cards}
    edges: dict[tuple, set] = defaultdict(set)

    def pair(a, b):
        return tuple(sorted((a, b)))

    # Signal: shared title root (all pairs inside a root group, capped so a huge group stays bounded)
    roots: dict[str, list[str]] = defaultdict(list)
    for c in doc_cards:
        r = extract_title_root(c.name)
        # Short roots (Law, MS, ME, SP) count only when the file also carries a position number
        if r and (len(r) > 3 or (len(r) >= 2 and c.position_in_family >= 0)):
            roots[r].append(c.path)
    for members in roots.values():
        members = members[:200]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                e = edges[pair(members[i], members[j])]
                e.add("title_root")
                a, b = by_path[members[i]], by_path[members[j]]
                if a.position_in_family >= 0 and b.position_in_family >= 0 and a.position_in_family != b.position_in_family:
                    e.add("numbering")

    # Signal: shared document code (FT-003_PAPER / FT-003_SCORED are one document's artifacts)
    codes: dict[str, list[str]] = defaultdict(list)
    for c in doc_cards:
        code = doc_code(c.name)
        if code:
            codes[code].append(c.path)
    for members in codes.values():
        members = members[:200]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                edges[pair(members[i], members[j])].add("doc_code")

    # Signal: resolved explicit link
    for c in doc_cards:
        for ref in c.references_to:
            if ref in by_path and ref != c.path:
                edges[pair(c.path, ref)].add("link")

    # Signal: distinctive vocabulary overlap
    vocab = {c.path: set([t for t in c.content_tokens if t not in STOPWORDS][:40]) for c in doc_cards}
    if len(doc_cards) <= VOCAB_PAIR_LIMIT:
        paths = [c.path for c in doc_cards]
        for i in range(len(paths)):
            va = vocab[paths[i]]
            if len(va) < 10:
                continue
            for j in range(i + 1, len(paths)):
                vb = vocab[paths[j]]
                if len(vb) < 10:
                    continue
                sim = len(va & vb) / math.sqrt(len(va) * len(vb))
                if sim >= VOCAB_NOMINATE:
                    edges[pair(paths[i], paths[j])].add("vocabulary")

    # Accept strong edges, keep weak ones for review
    parent = {p: p for p in by_path}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    weak = []
    for (a, b), ev in sorted(edges.items()):
        if "link" in ev or "doc_code" in ev or len(ev) >= 2:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        else:
            weak.append({"a": a, "b": b, "evidence": sorted(ev)})

    components: dict[str, list[str]] = defaultdict(list)
    for p in by_path:
        components[find(p)].append(p)

    families: list[Family] = []
    in_family: set[str] = set()
    for members in sorted((sorted(m) for m in components.values() if len(m) >= 2), key=lambda m: m[0].casefold()):
        mset = set(members)
        kinds = Counter()
        for (a, b), ev in edges.items():
            if a in mset and b in mset:
                kinds.update(ev)
        score = 1.0
        for k in kinds:
            score *= (1.0 - EVIDENCE_WEIGHT.get(k, 0.2))
        score = round(1.0 - score, 4)

        # Positions: unique slots, competing versions, gaps inside the observed range.
        # Position 0 is an index/readme, not a series slot. Files sharing one document code are
        # that document's artifacts (paper, facts card, scored copy), not competing versions.
        slots: dict[int, list[str]] = defaultdict(list)
        for p in members:
            pos = by_path[p].position_in_family
            if pos > 0:
                slots[pos].append(p)
        is_series = len(slots) >= 2
        gaps, completeness = [], 0.0
        if is_series:
            rng = range(min(slots), max(slots) + 1)
            gaps = [n for n in rng if n not in slots]
            completeness = round(len(slots) / len(rng), 4)
        competing = {}
        for k, v in sorted(slots.items()):
            slot_codes = {doc_code(by_path[p].name) for p in v}
            if len(v) > 1 and not (len(slot_codes) == 1 and "" not in slot_codes):
                competing[str(k)] = v
        fam_codes = Counter(doc_code(by_path[p].name) for p in members if doc_code(by_path[p].name))
        for code, n in sorted(fam_codes.items()):
            if n > 1:
                kinds[f"artifact_set[{code}]"] = n

        root_names = Counter(extract_title_root(by_path[p].name) for p in members)
        name = (root_names.most_common(1)[0][0] or Path(members[0]).stem).replace(" ", "_")
        if fam_codes and fam_codes.most_common(1)[0][1] * 2 >= len(members):
            name = fam_codes.most_common(1)[0][0]      # most members carry one document code: name it that
        fid = "FAM-" + hashlib.sha1("\n".join(members).encode("utf-8")).hexdigest()[:8]

        fam = Family(
            family_id=fid, family_name=name, members=members, member_count=len(members),
            evidence=[f"{k}:{n}" for k, n in sorted(kinds.items())],
            confidence=score, is_series=is_series, completeness=completeness, gaps=gaps,
            domain=Counter(by_path[p].domain for p in members).most_common(1)[0][0],
            competing_versions=competing,
        )
        families.append(fam)
        for p in members:
            c = by_path[p]
            c.family_id, c.family_name = fid, name
            c.relationship_strength = score
            c.orphan_probability = round(1.0 - score, 4)
            c.position_source = c.position_source or ""
        in_family |= mset

    weak_touch = {w["a"] for w in weak} | {w["b"] for w in weak}
    for c in doc_cards:
        if c.path not in in_family:
            c.family_id, c.family_name = "", ""
            c.relationship_strength = 0.3 if c.path in weak_touch else 0.0
            c.orphan_probability = 0.6 if c.path in weak_touch else 0.9
    return families, weak

# ── Output ───────────────────────────────────────────────────────────────────

def write_report(cards: list[FileCard], families: list[Family], stats: dict, output_dir: Path):
    """Write JSON + CSV reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # One run = one complete report. Remove anything a previous run left behind.
    for stale in ("deep_identify.json", "file_cards.csv", "families.csv", "orphans.csv"):
        (output_dir / stale).unlink(missing_ok=True)

    # Full JSON report
    report = {
        "schema": "david-os.deep-identify.v1",
        "stats": stats,
        "families": [asdict(f) for f in families],
        "cards": [asdict(c) for c in cards],
    }
    (output_dir / "deep_identify.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # File cards CSV — always published, header-only when empty
    if True:
        csv_fields = [
            "path", "name", "extension", "size_bytes", "file_kind", "domain",
            "domain_confidence", "doc_type", "doc_type_confidence",
            "family_id", "family_name", "position_in_family",
            "identity_confidence", "relationship_strength", "orphan_probability",
            "container_type", "is_protected", "can_move", "can_rename",
            "has_yaml_frontmatter", "section_count", "content_length",
        ]
        with (output_dir / "file_cards.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            w.writeheader()
            for card in sorted(cards, key=lambda c: (c.family_id or "ZZZ", c.position_in_family, c.name)):
                w.writerow(asdict(card))

    # Families CSV — always published
    if True:
        fam_fields = ["family_id", "family_name", "member_count", "is_series",
                       "confidence", "completeness", "gaps", "competing_versions", "domain", "evidence"]
        with (output_dir / "families.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fam_fields, extrasaction="ignore")
            w.writeheader()
            for fam in sorted(families, key=lambda f: -f.confidence):
                row = asdict(fam)
                row["gaps"] = ";".join(str(g) for g in fam.gaps)
                row["evidence"] = "; ".join(fam.evidence)
                row["competing_versions"] = json.dumps(fam.competing_versions, ensure_ascii=False) if fam.competing_versions else ""
                w.writerow(row)

    # Orphans CSV — always published
    orphans = [c for c in cards if c.orphan_probability > 0.5 and c.file_kind == "document"]
    if True:
        orph_fields = ["path", "name", "doc_type", "domain", "identity_confidence", "orphan_probability"]
        with (output_dir / "orphans.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=orph_fields, extrasaction="ignore")
            w.writeheader()
            for card in sorted(orphans, key=lambda c: -c.orphan_probability):
                w.writerow(asdict(card))

    print(f"Report written to {output_dir}")
    print(f"  Files scanned:  {stats['files_scanned']}")
    print(f"  Families found: {stats['families_found']}")
    print(f"  Orphans:        {stats['orphans']}")
    print(f"  Avg confidence: {stats['avg_identity_confidence']:.2%}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Deep file identification and series discovery")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan a folder")
    scan_p.add_argument("target", type=Path, help="Folder to scan")
    scan_p.add_argument("--output", type=Path, default=None, help="Report output directory")
    scan_p.add_argument("--max-files", type=int, default=2000)
    scan_p.add_argument("--lexicon", type=Path, default=None, help="Path to lexicon_canonical.json for overlay scoring")
    scan_p.add_argument("--series-only", action="store_true", help="Only report families, skip orphan detail")

    report_p = sub.add_parser("report", help="Print summary from existing report")
    report_p.add_argument("report_dir", type=Path)

    args = parser.parse_args()

    if args.command == "scan":
        output = args.output or Path(f"runs/deep_identify_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        cards, families, stats = scan_folder(args.target, args.max_files)

        # Lexicon overlay: re-score every card with the canonical vocabulary
        lexicon_path = args.lexicon or Path(__file__).parent / "lexicon_canonical.json"
        if lexicon_path.exists():
            from lexicon_overlay import LexiconOverlay
            lex = LexiconOverlay(lexicon_path)
            # Build text cache from cards that were read
            text_cache = {}
            for card in cards:
                if card.extraction_status == "read" and card.content_length > 0:
                    text_cache[card.path] = _read_sample(Path(card.path))
            lex.score_all(cards, stats, text_cache)
            print(f"  Lexicon overlay: {stats.get('lexicon_overlay', {}).get('cards_scored', 0)} cards scored")

        # Attention vectors: extract the 20-30 discriminative words per document
        attention_path = output / "attention"
        if text_cache:
            from attention_vector import AttentionEngine
            att = AttentionEngine(lexicon_path=lexicon_path if lexicon_path and lexicon_path.exists() else None)
            att.ingest(text_cache)
            att.export(attention_path)
            # Write nearest-neighbors for each family member
            for fam in families:
                for member in fam.members:
                    vec = att.vector(member)
                    if vec:
                        card = next((c for c in cards if c.path == member), None)
                        if card:
                            neighbors = att.nearest(member, k=3)
                            card.content_tokens = [t for t, _ in vec.terms[:30]]  # replace with attention terms

        write_report(cards, families, stats, output)

    elif args.command == "report":
        data = json.loads((args.report_dir / "deep_identify.json").read_text(encoding="utf-8"))
        s = data["stats"]
        print(f"Target:     {s['target']}")
        print(f"Container:  {s['container_type']} (protected={s['container_protected']})")
        print(f"Scanned:    {s['files_scanned']} files")
        print(f"Families:   {s['families_found']}")
        print(f"Orphans:    {s['orphans']}")
        print(f"Confidence: {s['avg_identity_confidence']:.2%}")
        print(f"\nDomains:    {s['domain_distribution']}")
        print(f"Doc types:  {s['doc_type_distribution']}")
        if data["families"]:
            print(f"\nFamilies:")
            for fam in data["families"]:
                series_tag = f" [SERIES pos {fam.get('gaps', [])} gaps]" if fam["is_series"] else ""
                print(f"  {fam['family_id']}: {fam['family_name']} ({fam['member_count']} files, {fam['confidence']:.0%}){series_tag}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
