"""
FIS Classifier — Folder type + File CHI scoring (the master equation).

Two distinct classification passes, always in this order:

  PASS 1: FOLDER ROLE
    → system / media / document / project / dump / archive
    → Folder role gates what actions are even allowed on files inside.
    → A file inside a system folder is PIN-ONLY regardless of its content.

  PASS 2: FILE CHI SCORE  (only if folder allows it)
    → 12 variables scored 1-3:
        G M E S T K R Q F C  (10 CHI factors from χ = ∭(G·M·E·S·T·K·R·Q·F·C) dx dy dt)
        Domain                (top matching domain: physics/theology/code/etc.)
        Law                   (top matching law: L01-L10)
    → Dominant CHI factor = primary file role
    → Score sum = overall classification confidence

  FALLBACK:
    → If confidence < FALLBACK_THRESHOLD, call Claude API (if key available)
    → Claude returns structured JSON with same shape

Usage:
    from fis_classifier import classify_folder, classify_file, FolderClass
"""

import json, os, re
from collections import Counter
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Tag 4: Content type  (what the file IS as a functional object)
# ---------------------------------------------------------------------------

_CT = {}
for _keys, _val in [
    ([".py",".js",".ts",".jsx",".tsx",".css",".scss",".sh",".bat",".ps1",
      ".ahk",".ahk2",".c",".cpp",".h",".cs",".java",".go",".rs",".rb",
      ".php",".swift",".kt",".lua"], "code"),
    ([".json",".csv",".tsv",".xlsx",".xls",".ods",".db",".sqlite",".parquet"], "data"),
    ([".yaml",".yml",".toml",".ini",".cfg",".env",".gitignore",".editorconfig"], "config"),
    ([".pdf",".docx",".doc",".rtf",".odt",".pptx",".ppt"], "document"),
    ([".md",".markdown",".txt",".rst",".log"], "note"),
    ([".lean",".tex",".bib",".coq"], "proof"),
    ([".jpg",".jpeg",".png",".gif",".webp",".svg",".bmp",".tiff",".psd",
      ".ai",".raw",".cr2"], "image"),
    ([".mp4",".mov",".avi",".mkv",".wmv",".m4v",".webm"], "video"),
    ([".mp3",".wav",".flac",".aac",".ogg",".m4a",".opus"], "audio"),
]:
    for _k in _keys:
        _CT[_k] = _val
CONTENT_TYPE_MAP = _CT

def detect_content_type(ext: str, sample: str = "") -> str:
    """Tag 4: what the file IS as a functional object."""
    ct = CONTENT_TYPE_MAP.get(ext.lower())
    if ct:
        return ct
    # keyword fallback for text files with ambiguous extension
    if sample:
        low = sample.lower()
        if any(w in low for w in ("theorem","proof","lemma","axiom","∀","∃")): return "proof"
        if any(w in low for w in ("abstract","introduction","conclusion","bibliography")): return "paper"
        if any(w in low for w in ("def ","class ","import ","function ","return ")): return "code"
        if any(w in low for w in ("sermon","congregation","homily","preach")): return "sermon"
    return "document"  # safe default for unrecognised text; "binary" for blobs handled below

# ---------------------------------------------------------------------------
# Tag 5: Evidence density  (how empirically grounded is the content)
# ---------------------------------------------------------------------------

EVIDENCE_TERMS = {
    "data","dataset","measurement","measured","experiment","observation",
    "citation","source","reference","test","prediction","empirical","study",
    "sigma","p-value","sample","peer-reviewed","replication","statistical",
    "correlation","regression","hypothesis","result","finding","evidence",
}

FRUIT_TERMS = {
    "love","joy","peace","patience","kindness","goodness","faithfulness",
    "gentleness","self-control","hope","grace","humility","unity","truth",
    "care","restore","forgive","dignity","mercy","repair","shalom","agape",
}

ANTI_FRUIT_TERMS = {
    "hatred","despair","anxiety","impatience","cruelty","corruption",
    "betrayal","harshness","addiction","rage","domination","coercion",
    "dehumanization","panic","scapegoat","manipulate","contempt","abuse",
}

try:
    from structural_evidence import score_structural_evidence
except ImportError:
    score_structural_evidence = None

def _score_terms(text: str, terms: set, cap: int = 8) -> float:
    """Return 0-100 score of how many terms from the set appear in text."""
    low  = text.lower()
    hits = sum(1 for t in terms if t in low)
    return round(min(100.0, (hits / cap) * 100.0), 1)

def score_evidence(text: str) -> float:
    if score_structural_evidence:
        return score_structural_evidence(text)["total_score"]
    return _score_terms(text, EVIDENCE_TERMS, cap=8)

def score_fruit(text: str) -> float:
    return _score_terms(text, FRUIT_TERMS, cap=6)

def score_anti_fruit(text: str) -> float:
    return _score_terms(text, ANTI_FRUIT_TERMS, cap=5)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FALLBACK_THRESHOLD = 0.45   # call AI when local confidence is below this

# System/software dependency markers — if found, folder is SYSTEM, touch nothing inside
SYSTEM_MARKERS = {
    "files": {
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "requirements.txt", "requirements.in", "pyproject.toml", "setup.py", "setup.cfg",
        "pipfile", "pipfile.lock", "cargo.toml", "cargo.lock",
        "go.mod", "go.sum", "composer.json",
        "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "makefile", "cmake", "cmakelists.txt",
        ".env", ".env.local", ".env.example",
        "*.sln", "*.csproj", "*.vbproj",
        "webpack.config.js", "vite.config.ts", "rollup.config.js",
        "tsconfig.json", "jsconfig.json", ".babelrc",
        ".eslintrc", ".prettierrc",
        "manage.py",                        # django
        "artisan",                          # laravel
        "gemfile", "gemfile.lock",
    },
    "dirs": {
        ".git", ".svn", ".hg",
        "node_modules", ".venv", "venv", "__pycache__",
        "src", "dist", "build", "target", "out", "bin", "obj",
        "migrations", "static", "templates", "public",
        ".next", ".nuxt", ".svelte-kit",
        "vendor", "packages",
    }
}

# Extension family groups
MEDIA_EXTS   = {".jpg",".jpeg",".png",".gif",".webp",".svg",".bmp",".tiff",".tif",
                ".mp4",".mov",".avi",".mkv",".wmv",".m4v",".webm",
                ".mp3",".wav",".flac",".aac",".ogg",".m4a",".opus",
                ".psd",".ai",".sketch",".fig",".xcf",".raw",".cr2",".nef"}
DOC_EXTS     = {".pdf",".docx",".doc",".rtf",".odt",".pptx",".ppt",
                ".xlsx",".xls",".ods",".csv",".tsv",".numbers",".key"}
TEXT_EXTS    = {".md",".markdown",".txt",".rst",".log"}
CODE_EXTS    = {".py",".js",".ts",".jsx",".tsx",".css",".scss",".html",".htm",
                ".xml",".json",".yaml",".yml",".toml",".ini",".cfg",".sh",
                ".bat",".ps1",".ahk",".sql",".c",".cpp",".h",".cs",".java",
                ".go",".rs",".rb",".php",".swift",".kt"}

# BAD name patterns → dump indicator
BAD_NAME_RE = re.compile(
    r"\b(final|copy|new|old|backup|bak|temp|tmp|untitled|misc|stuff|"
    r"test|draft|version|v\d|revised|edit|updated|wip|junk|random|"
    r"asdf|qwerty|\(\d+\)|_\d{3,})\b", re.I
)

# ---------------------------------------------------------------------------
# CHI factor keyword signals  (the 12-variable master equation)
# ---------------------------------------------------------------------------

CHI_SIGNALS = {
    "G": {
        "name": "Grace",
        "law": "L01/L08",
        "keywords": [
            "grace","charis","gravitational","curvature","spacetime","geodesic",
            "gift","unmerited","favor","negentropic","provision","sovereign",
            "sustain","external source","persistent source","common grace",
            "gravity","einstein","tensor","manifold","frame independent",
        ]
    },
    "M": {
        "name": "Moral Alignment",
        "law": "L02",
        "keywords": [
            "moral","alignment","will","repentance","conversion","momentum",
            "inertia","obedience","surrender","submission","sanctification",
            "moral mass","m_eff","effective mass","force","acceleration",
            "resistance","sin nature","flesh","free will",
        ]
    },
    "E": {
        "name": "Truth Signal",
        "law": "L03",
        "keywords": [
            "truth","deception","witness","testimony","light","electromagnetic",
            "maxwell","glory","doxa","revelation","signal","noise","logos",
            "scripture","evidence","data","empirical","statistical","measure",
            "falsify","testable","hypothesis","verify","prediction","result",
        ]
    },
    "S": {
        "name": "Entropy",
        "law": "L05",
        "keywords": [
            "entropy","thermodynamic","second law","heat death","disorder",
            "chaos","judgment","justice","free energy","boltzmann","decay",
            "adversary","corruption","decoherence","dissipation","equilibrium",
            "irreversible","arrow of time","loss","noise","drift","attenuation",
        ]
    },
    "T": {
        "name": "Time / Kairos",
        "law": "L08",
        "keywords": [
            "time","kairos","chronos","temporal","duration","epoch","timeline",
            "history","sequence","order","moment","period","future","past",
            "relativity","lorentz","proper time","dilation","symmetry",
        ]
    },
    "K": {
        "name": "Knowledge",
        "law": "L06",
        "keywords": [
            "knowledge","information","shannon","logos","word","channel","capacity",
            "bandwidth","sanctification","logos","data","encoding","fidelity",
            "compression","transmission","noise","signal-to-noise",
            "epistemology","axiom","foundation","ground","method",
        ]
    },
    "R": {
        "name": "Relational Frame",
        "law": "L08",
        "keywords": [
            "relation","frame","reference","covenant","community","fellowship",
            "bond","connection","love","agape","relationship","binding",
            "lorentz","invariant","frame lock","mutual","partnership",
        ]
    },
    "Q": {
        "name": "Quantum / Uncertainty",
        "law": "L07",
        "keywords": [
            "quantum","collapse","superposition","measurement","faith","observer",
            "uncertainty","doubt","probability","wave function","planck",
            "hilbert","entanglement","coherence","decoherence","interference",
        ]
    },
    "F": {
        "name": "Faith / Fruit",
        "law": "L04/L07",
        "keywords": [
            "faith","trust","belief","hope","fruit","love","joy","peace",
            "patience","kindness","goodness","faithfulness","gentleness",
            "self-control","strong force","quark","binding","covenant",
            "confinement","agape","yukawa",
        ]
    },
    "C": {
        "name": "Christ Alignment / Coherence",
        "law": "L10",
        "keywords": [
            "christ","coherence","integration","shalom","kingdom","master equation",
            "decoherence","alignment","logos","salvation","cross","resurrection",
            "trinity","atonement","redemption","reconciliation","mediator",
            "coherent","integrated","unified","complete","perfect",
        ]
    },
}

DOMAIN_SIGNALS = {
    "physics":       ["physics","quantum","field","entropy","thermodynamic","relativity",
                      "gravity","mass","energy","wave","particle","tensor","lagrangian"],
    "theology":      ["god","christ","jesus","spirit","grace","sin","salvation","cross",
                      "resurrection","trinity","logos","scripture","biblical","mercy"],
    "epistemology":  ["truth","knowledge","axiom","foundation","munchhausen","circular",
                      "regress","assumption","falsifiability","prediction","method"],
    "morality":      ["good","evil","justice","moral","ought","obligation","duty",
                      "virtue","consequence","accountability","ethics"],
    "consciousness": ["consciousness","observer","experience","qualia","mind",
                      "cognition","brain","neural","subjective","perception"],
    "information":   ["information","signal","noise","channel","compression","shannon",
                      "encoding","transmission","fidelity"],
    "code":          ["function","class","import","return","variable","algorithm",
                      "database","api","server","client","deploy","test","debug"],
    "media":         ["image","video","audio","photo","render","design","clip","frame",
                      "resolution","pixel","color","layer","export"],
    "document":      ["chapter","section","abstract","introduction","conclusion",
                      "bibliography","reference","table","figure","appendix"],
    "data":          ["row","column","header","sheet","cell","formula","pivot",
                      "dataset","csv","table","query","aggregate"],
}

LAW_SIGNALS = {
    "L01": ["gravity","curvature","spacetime","mass","grace","attract","geodesic"],
    "L02": ["motion","force","will","repentance","momentum","acceleration","inertia"],
    "L03": ["electromagnetic","maxwell","light","truth","deception","witness","signal"],
    "L04": ["strong force","quark","binding","love","covenant","confinement","agape"],
    "L05": ["entropy","thermodynamic","justice","mercy","judgment","free energy","decay"],
    "L06": ["information","shannon","channel","logos","word","noise","sanctification"],
    "L07": ["quantum","collapse","superposition","faith","observer","doubt","uncertainty"],
    "L08": ["relativity","frame","lorentz","relationship","reference","invariant"],
    "L09": ["weak force","decay","parity","atonement","moral conservation","irreversible"],
    "L10": ["coherence","christ","integration","shalom","kingdom","master equation"],
}

# ---------------------------------------------------------------------------
# Data classes (plain dicts for easy JSON serialisation)
# ---------------------------------------------------------------------------

class FolderClass:
    SYSTEM   = "system"    # software/code — PIN ONLY
    MEDIA    = "media"     # images/video/audio dominant
    DOCUMENT = "document"  # PDF/DOCX/XLSX dominant
    PROJECT  = "project"   # mixed intentional bundle
    DUMP     = "dump"      # unorganised holding pile
    ARCHIVE  = "archive"   # old but coherent, low activity

ALLOWED_ACTIONS = {
    FolderClass.SYSTEM:   ["index", "hash", "report_duplicates", "flag_suspicious"],
    FolderClass.MEDIA:    ["rename", "sort_date", "sort_type", "dedupe", "archive"],
    FolderClass.DOCUMENT: ["rename", "extract", "classify", "move", "dedupe", "version_rank"],
    FolderClass.PROJECT:  ["index", "rename_internal", "subfolder_sort", "archive_exports"],
    FolderClass.DUMP:     ["triage", "quarantine", "group_obvious", "dedupe", "rename_high_confidence"],
    FolderClass.ARCHIVE:  ["index", "compress", "verify_integrity"],
}

FORBIDDEN_ACTIONS = {
    FolderClass.SYSTEM:   ["rename", "move", "delete", "merge", "split", "reorganize"],
    FolderClass.PROJECT:  ["global_scatter", "delete_uncertain", "rename_dependency_files"],
}

# ---------------------------------------------------------------------------
# Folder classifier
# ---------------------------------------------------------------------------

def classify_folder(folder_path: str) -> dict:
    """
    Returns:
        {
            "folder_class": FolderClass.*,
            "confidence": 0.0-1.0,
            "dependency_risk": 0.0-1.0,
            "dominant_family": "media"|"document"|"code"|"mixed",
            "dominant_ratio": 0.0-1.0,
            "file_count": int,
            "system_markers_found": [...],
            "allowed_actions": [...],
            "forbidden_actions": [...],
            "notes": [...],
        }
    """
    p = Path(folder_path)
    if not p.is_dir():
        return {"folder_class": FolderClass.DUMP, "confidence": 0.0, "error": "not a directory"}

    # --- collect files (shallow, max 500 for speed) ---
    try:
        entries = list(p.iterdir())
    except PermissionError:
        return {"folder_class": FolderClass.SYSTEM, "confidence": 0.9,
                "error": "permission_denied", "dependency_risk": 0.9}

    files     = [e for e in entries if e.is_file()]
    subdirs   = [e for e in entries if e.is_dir()]
    file_count = len(files)
    notes     = []

    # --- PASS 1: system / dependency markers ---
    system_markers_found = []
    file_names_lower = {f.name.lower() for f in files}
    dir_names_lower  = {d.name.lower() for d in subdirs}

    for marker in SYSTEM_MARKERS["files"]:
        if marker.startswith("*"):
            ext = marker[1:]
            if any(f.suffix.lower() == ext for f in files):
                system_markers_found.append(marker)
        elif marker in file_names_lower:
            system_markers_found.append(marker)

    for marker in SYSTEM_MARKERS["dirs"]:
        if marker in dir_names_lower:
            system_markers_found.append(f"dir:{marker}")

    dependency_risk = min(1.0, len(system_markers_found) / 3.0)

    if len(system_markers_found) >= 2:
        return {
            "folder_class":          FolderClass.SYSTEM,
            "confidence":            min(0.95, 0.6 + len(system_markers_found) * 0.1),
            "dependency_risk":       dependency_risk,
            "dominant_family":       "code",
            "dominant_ratio":        1.0,
            "file_count":            file_count,
            "system_markers_found":  system_markers_found,
            "allowed_actions":       ALLOWED_ACTIONS[FolderClass.SYSTEM],
            "forbidden_actions":     FORBIDDEN_ACTIONS[FolderClass.SYSTEM],
            "notes":                 [f"System markers: {', '.join(system_markers_found[:6])}"],
        }

    # --- PASS 2: extension family distribution ---
    ext_counts: Counter = Counter()
    bad_name_count = 0
    for f in files[:300]:
        ext = f.suffix.lower()
        if ext in MEDIA_EXTS:   ext_counts["media"] += 1
        elif ext in DOC_EXTS:   ext_counts["document"] += 1
        elif ext in CODE_EXTS:  ext_counts["code"] += 1
        elif ext in TEXT_EXTS:  ext_counts["text"] += 1
        else:                   ext_counts["other"] += 1
        if BAD_NAME_RE.search(f.stem):
            bad_name_count += 1

    total = max(1, file_count)
    bad_ratio = bad_name_count / total

    dominant_family, dominant_count = ext_counts.most_common(1)[0] if ext_counts else ("other", 0)
    dominant_ratio = dominant_count / total

    # --- PASS 3: classify from distribution ---

    # Archive: few recent files, old mtime, coherent
    if file_count < 50 and _folder_is_old(p, days=180) and dominant_ratio > 0.6:
        fc = FolderClass.ARCHIVE
        conf = 0.7

    # Media: overwhelmingly images/video/audio, no software markers
    elif dominant_family == "media" and dominant_ratio > 0.80 and dependency_risk < 0.3:
        fc   = FolderClass.MEDIA
        conf = dominant_ratio

    # Document: overwhelmingly PDFs/office docs
    elif dominant_family == "document" and dominant_ratio > 0.65 and dependency_risk < 0.3:
        fc   = FolderClass.DOCUMENT
        conf = dominant_ratio

    # Dump: high bad-name ratio OR very large mixed collection
    elif bad_ratio > 0.35 or (file_count > 200 and dominant_ratio < 0.5):
        fc   = FolderClass.DUMP
        conf = min(0.85, 0.5 + bad_ratio)
        notes.append(f"{bad_name_count}/{file_count} files have dump-style names")

    # Project: mixed but below dump threshold
    else:
        fc   = FolderClass.PROJECT
        conf = 0.6

    return {
        "folder_class":         fc,
        "confidence":           round(conf, 3),
        "dependency_risk":      round(dependency_risk, 3),
        "dominant_family":      dominant_family,
        "dominant_ratio":       round(dominant_ratio, 3),
        "file_count":           file_count,
        "system_markers_found": system_markers_found,
        "ext_distribution":     dict(ext_counts),
        "bad_name_ratio":       round(bad_ratio, 3),
        "allowed_actions":      ALLOWED_ACTIONS.get(fc, []),
        "forbidden_actions":    FORBIDDEN_ACTIONS.get(fc, []),
        "notes":                notes,
    }


def _folder_is_old(p: Path, days: int = 180) -> bool:
    import time
    cutoff = time.time() - days * 86400
    try:
        return p.stat().st_mtime < cutoff
    except OSError:
        return False


# ---------------------------------------------------------------------------
# File CHI scorer  (the master equation: 12 variables scored 0-3)
# ---------------------------------------------------------------------------

def score_chi_factor(text: str, factor_key: str) -> int:
    """Return 0-3 score for one CHI factor based on keyword hits in text."""
    keywords = CHI_SIGNALS[factor_key]["keywords"]
    low      = text.lower()
    hits     = sum(1 for kw in keywords if kw in low)
    if hits == 0:   return 0
    if hits <= 2:   return 1
    if hits <= 5:   return 2
    return 3


def score_domain(text: str) -> tuple[str, int]:
    """Return (top_domain, score 0-3)."""
    low    = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_SIGNALS.items():
        hits = sum(1 for kw in keywords if kw in low)
        if hits:
            scores[domain] = hits
    if not scores:
        return "unknown", 0
    top = max(scores, key=scores.get)
    hits = scores[top]
    return top, min(3, 1 + hits // 3)


def score_law(text: str) -> tuple[str, int]:
    """Return (top_law, score 0-3)."""
    low    = text.lower()
    scores = {}
    for law, keywords in LAW_SIGNALS.items():
        hits = sum(1 for kw in keywords if kw in low)
        if hits:
            scores[law] = hits
    if not scores:
        return "none", 0
    top  = max(scores, key=scores.get)
    hits = scores[top]
    return top, min(3, 1 + hits // 2)


# ---------------------------------------------------------------------------
# SECOND AXIS: DOCUMENT TYPE  (what the file IS as a document, not what it is about)
#
# The CHI/domain/law pass above scores WHAT a document is about.
# This pass scores WHAT TYPE of document it is. The two axes are orthogonal:
# an AXIOM and a NARRATIVE can both be dominant-C theology files.
#
# Each type carries weighted regex signals. Weight reflects how *exclusive*
# the signal is to that type, not how common it is:
#     3.0  near-decisive marker (effectively only this type produces it)
#     2.0  strong marker
#     1.0  supporting marker
#     0.5  weak / shared marker
# ---------------------------------------------------------------------------

DOC_TYPES = (
    "AXIOM", "CANON", "DERIVATION", "NARRATIVE", "ARTICLE",
    "WORKING_NOTE", "DUMP", "EVIDENCE", "BRIDGE",
)

# (pattern, weight, human-readable label for the evidence trail)
DOC_TYPE_SIGNALS = {
    "AXIOM": [
        (r"^\s*axiom_id\s*:",                       3.0, "axiom_id frontmatter"),
        (r"^\s*chain_position\s*:",                 3.0, "chain_position frontmatter"),
        (r"\b(PRIMITIVE|DERIVED|STANCE)\b",         2.0, "PRIMITIVE/DERIVED/STANCE label"),
        (r"kill\s+condition",                       3.0, "kill condition"),
        (r"^##\s*Formal\s+Statement",               2.5, "Formal Statement heading"),
        (r"^##\s*Assumes",                          2.0, "Assumes heading"),
        (r"^\s*depends_on\s*:",                     2.0, "depends_on frontmatter"),
        (r"^\s*enables\s*:",                        1.5, "enables frontmatter"),
        (r"\bA\d+\.\d+\b",                          1.5, "A1.1-style axiom numbering"),
        (r"\b(META-\d|FINAL-\d|CLOSURE)\b",         1.5, "meta/final axiom id"),
        (r"^\s*(tier|stage)\s*:\s*\d",              1.0, "tier/stage frontmatter"),
        (r"\baxiom(s)?\b",                          0.5, "the word axiom"),
        (r"\bprimitive\b",                          0.5, "primitive"),
    ],
    "CANON": [
        # Decisive: these appear when a document IS the ruling, not about one.
        (r"^#+\s*(RULING|VERDICT|CANON DECISION)\b", 3.0, "ruling heading"),
        (r"\bLEAN[\s\-]?VERIFIED\b",                3.0, "LEAN-VERIFIED"),
        (r"\bblue[\s_-]?sheet\b",                   3.0, "blue sheet marker"),
        (r"^\s*(status|ruling|verdict)\s*:\s*\w",   2.5, "status/ruling field"),
        (r"\bRULED\b|\bRULING\b",                   2.0, "RULED/RULING"),
        (r"\bLOCKED\b",                             2.0, "LOCKED"),
        (r"\bratifi(ed|cation)\b",                  2.0, "ratification"),
        (r"\bfreeze[\s_-]?candidate\b",             2.0, "freeze candidate"),
        (r"\bstanding\s+canon\b",                   2.0, "standing canon"),
        (r"\bsource[\s_-]of[\s_-]truth\b",          1.5, "source of truth"),
        (r"\bsupersede[sd]?\b",                     1.5, "supersedes"),
        (r"\bdo[\s_-]not[\s_-]touch\b",             1.5, "do-not-touch"),
        # Ambient in this corpus - supporting evidence only, never decisive.
        (r"\bcanonical\b|\bCANON\b",                0.75, "canonical/CANON (ambient)"),
        (r"\bT5\b",                                 0.75, "T5 tier"),
    ],
    "DERIVATION": [
        (r"\bderives?\s+from\b",                    3.0, "derives from"),
        (r"\bderivation\s+(chain|step|tree)\b",     2.5, "derivation chain/step"),
        (r"\bparent\s+node\b",                      2.5, "parent node"),
        (r"\bproof\s+receipt\b",                    3.0, "proof receipt"),
        (r"^\s*(Proof|Lemma|Theorem|Corollary)\b",  2.0, "proof/lemma/theorem block"),
        (r"\bQ\.?E\.?D\.?\b|∎",                2.0, "QED"),
        (r"\bstep\s*\d+\s*[:.—-]",             1.5, "numbered derivation steps"),
        (r"⇒|⊢|\\vdash|\\implies",        1.5, "implication operators"),
        (r"\btherefore\b|\bhence\b|\bit follows\b", 1.0, "inferential connectives"),
        (r"\bsorry\b|\badmit\b|lake\s+build",       1.5, "Lean build artifacts"),
    ],
    "NARRATIVE": [
        (r"\bIn the beginning\b",                   3.0, "In the beginning"),
        (r"\b(Galatians|Genesis|Romans|John|Matthew|Psalm|Isaiah|Hebrews|Corinthians)\s+\d+",
                                                    2.0, "scripture citation"),
        (r"\bonce\s+(there\s+was|upon)\b",          2.5, "story opener"),
        (r"\b(he|she|they)\s+said\b",               1.0, "dialogue attribution"),
        (r"^>\s+\S",                                1.0, "block quotation"),
        (r"\bchapter\s+\d+\b",                      1.0, "chapter marker"),
        (r"\bstory\b|\bparable\b|\btestimony\b",    1.0, "story/parable/testimony"),
        (r"\bI\s+(was|had|remember|walked|sat)\b",  1.5, "first-person narration"),
    ],
    "ARTICLE": [
        (r"\bSubstack\b",                           3.0, "Substack marker"),
        (r"\bOpening\s+Device\b",                   3.0, "Opening Device"),
        (r"\btheopoetic\b",                         3.0, "theopoetic engine"),
        (r"\bsubscribe\b|\bpaid\s+subscriber\b",    2.0, "subscribe call"),
        (r"^\s*(subtitle|byline|dek)\s*:",          2.0, "article frontmatter"),
        (r"\bpostType\s*:\s*post\b",                2.5, "post frontmatter"),
        (r"\bread\s+more\b|\bshare\s+this\b",       1.0, "publication furniture"),
        (r"\bpart\s+\d+\s+of\s+\d+\b",              1.0, "series positioning"),
    ],
    "WORKING_NOTE": [
        (r"\bTODO\b",                               2.5, "TODO"),
        (r"\bPENDING\b",                            2.5, "PENDING"),
        (r"\bFORMATION[\s_-]STAGE\b",               3.0, "FORMATION-STAGE"),
        (r"\bsession\s+log\b|\btrench\s+report\b",  2.5, "session log"),
        (r"\bharvest\b",                            2.0, "harvest doc"),
        (r"^\s*[-*]\s+\[\s?\]",                     2.0, "unchecked task box"),
        (r"\bNEXT\s+STEPS?\b",                      2.0, "next steps"),
        (r"\bWIP\b|\bwork[\s\-]in[\s\-]progress\b", 2.0, "WIP"),
        (r"\bSTATUS\s*:",                           1.0, "status line"),
        (r"\bscratch\b|\bnotes?\s+to\s+self\b",     1.5, "scratch notes"),
        (r"^#+\s*.*\b(sweep|housekeeping|cleanup|audit)\s+(report|log)\b", 3.0, "sweep/audit report heading"),
        (r"^\s*\*\*(Scope|Date|Patterns swept|Rule applied)\*\*\s*:", 2.5, "report header block"),
        (r"^#+\s*(FIXED|SKIPPED|FLAGGED|EXCLUSIONS)\b", 2.0, "report outcome section"),
        (r"\b\d+\s+files?\s+(fixed|scanned|swept|flagged|moved)\b", 2.0, "file-count outcome"),
    ],
    "EVIDENCE": [
        (r"\bPEAR[\s\-]?LAB\b",                     3.0, "PEAR-LAB"),
        (r"\d+(\.\d+)?\s*sigma\b|σ\s*=",       3.0, "sigma value"),
        (r"\bp[\s\-]?value\b|\bp\s*[<=]\s*0?\.\d+", 2.5, "p-value"),
        (r"\bet\s+al\.",                            2.0, "citation et al."),
        (r"\bdoi\s*:|\bdoi\.org",                   2.5, "DOI"),
        (r"\barXiv\b|\bPubMed\b|\bOpenAlex\b|\bCrossref\b", 2.0, "repository citation"),
        (r"\bn\s*=\s*\d+",                          1.5, "sample size"),
        (r"\bconfidence\s+interval\b|\bCI\s*[:=]",  1.5, "confidence interval"),
        (r"\breplicat(ed|ion)\b|\bpre[\s\-]?registered\b", 1.5, "replication/preregistration"),
        (r"\bcorrelat(ion|ed)\b|\bregression\b",    1.0, "statistical language"),
        (r"\bexperiment\b|\bdataset\b",             1.0, "experiment/dataset"),
    ],
    "BRIDGE": [
        (r"\bisomorph(ism|ic)\b",                   3.0, "isomorphism"),
        (r"\bcorrespondence\b",                     2.5, "correspondence"),
        (r"\bmaps?\s+(on)?to\b",                    2.0, "maps to"),
        (r"\bB[0-6]\b\s*(grade|grading|:)",         3.0, "B0-B6 grading"),
        (r"\bstructural\s+(identity|transport)\b",  2.5, "structural identity/transport"),
        (r"\bcross[\s\-]domain\b",                  2.0, "cross-domain"),
        (r"\bbridge\b",                             1.5, "bridge"),
        (r"\b(Physics|Theology|Quantum|Scripture)\s+mapping\s*:", 2.0, "explicit mapping table"),
        (r"↔",                                 1.5, "bidirectional arrow"),
    ],
    # DUMP has no positive keyword signals - it is diagnosed structurally below.
    "DUMP": [],
}

# Per-type normaliser: the score at which a type is considered fully expressed.
# Tuned so a clear exemplar lands near 1.0 without needing every signal present.
# A signal must be at least this heavy before the filename is allowed to
# contribute to it. Keeps ambient words in names from deciding the type.
_NAME_VOTE_MIN_WEIGHT = 2.0

DOC_TYPE_NORM = {
    "AXIOM":        9.0,
    "CANON":        8.5,
    "DERIVATION":   7.0,
    "NARRATIVE":    6.0,
    "ARTICLE":      6.0,
    "WORKING_NOTE": 6.0,
    "EVIDENCE":     7.0,
    "BRIDGE":       7.0,
    "DUMP":         3.0,
}

# Compiled once at import - these run over every file in the corpus.
_DOC_TYPE_RX = {
    t: [(re.compile(p, re.IGNORECASE | re.MULTILINE), w, label)
        for p, w, label in sigs]
    for t, sigs in DOC_TYPE_SIGNALS.items()
}

# Order used to break exact ties: more structurally committed types win.
_TYPE_PRIORITY = ["AXIOM", "CANON", "DERIVATION", "BRIDGE", "EVIDENCE",
                  "ARTICLE", "NARRATIVE", "WORKING_NOTE", "DUMP"]


_HTML_DOC_RX  = re.compile(r"<(html|body|div|p|h[1-6]|section|article)\b", re.IGNORECASE)
_HTML_HEAD_RX = re.compile(r"<h[1-6]\b", re.IGNORECASE)
_SCRIPT_RX    = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RX       = re.compile(r"<[^>]+>")


def looks_like_html(text: str) -> bool:
    """
    True when the sample carries real document markup, not a stray angle bracket.

    A generated page can open with kilobytes of inline <style> before its first
    body tag, so the doctype/<html> declaration counts on its own and the tag
    census runs over a wide window rather than the first few lines.
    """
    head = text[:2000].lstrip().lower()
    if head.startswith("<!doctype html") or head.startswith("<html"):
        return True
    return len(_HTML_DOC_RX.findall(text[:40000])) >= 2


def html_to_text(text: str) -> tuple[str, int]:
    """
    Strip markup for structural analysis, returning (text, heading_count).

    Without this an HTML page reads as zero headings and lands in DUMP purely
    because its headings are <h2> instead of "##".
    """
    headings = len(_HTML_HEAD_RX.findall(text))
    body     = _SCRIPT_RX.sub(" ", text)
    body     = _TAG_RX.sub("\n", body)
    body     = re.sub(r"&[a-z]+;|&#\d+;", " ", body)
    body     = re.sub(r"\n{3,}", "\n\n", body)
    return body, headings


def _structural_features(text: str, html_headings: int = 0) -> dict:
    """Shape metrics that do not depend on vocabulary."""
    lines      = text.splitlines()
    nonblank   = [ln for ln in lines if ln.strip()]
    words      = re.findall(r"[A-Za-z']+", text)
    headings   = sum(1 for ln in lines if ln.lstrip().startswith("#")) + html_headings
    list_lines = sum(1 for ln in lines if re.match(r"\s*([-*+]|\d+\.)\s+", ln))
    # Lexical diversity stands in for entropy: a high unique-word ratio over a
    # short document is the signature of pasted, unrelated fragments.
    uniq_ratio = (len(set(w.lower() for w in words)) / len(words)) if words else 0.0
    return {
        "chars":           len(text),
        "lines":           len(lines),
        "nonblank_lines":  len(nonblank),
        "words":           len(words),
        "headings":        headings,
        "list_lines":      list_lines,
        "has_frontmatter": bool(re.match(r"\s*---\s*\n", text)),
        "heading_density": round(headings / max(1, len(nonblank)), 3),
        "uniq_ratio":      round(uniq_ratio, 3),
        "avg_line_len":    round(sum(len(ln) for ln in nonblank) / max(1, len(nonblank)), 1),
    }


# A file longer than this is substantive work even when it matches no type
# signature; calling it a DUMP would be a false negative, not a diagnosis.
DUMP_MAX_WORDS = 800


def _dump_score(feat: dict, best_other: float) -> float:
    """
    DUMP is the absence of structure, so it is scored from shape only:
    short, unheaded, lexically scattered, and not strongly anything else.

    Length is a hard gate. A long unstructured document is UNCLASSIFIED
    (see classify_document_type) - it is not a dump.
    """
    if feat["words"] > DUMP_MAX_WORDS:
        return 0.0
    s = 0.0
    if feat["words"] < 250:                              s += 1.0
    if feat["words"] < 80:                               s += 1.0
    if feat["headings"] == 0:                            s += 1.0
    if not feat["has_frontmatter"]:                      s += 0.5
    if feat["uniq_ratio"] > 0.72 and feat["words"] > 20: s += 1.0
    if feat["avg_line_len"] > 400:                       s += 0.5   # one pasted wall
    if best_other >= 0.35:                               s -= 2.0   # it IS something else
    return max(0.0, s)


def classify_document_type(text: str, name: str = "", path: str = "") -> dict:
    """
    Second classification axis: WHAT TYPE of document this is.

    Returns one primary type, a 0-1 confidence, the full normalised score
    vector, and the matched evidence for the winning type, so the call can be
    audited rather than trusted.
    """
    # The filename is evidence, but a name like "03-the-master-equation.canonical.md"
    # must not by itself decide the type. The name is only offered to decisive
    # signals; weak/ambient signals see the body alone.
    # Markup is stripped first so an HTML page is judged on its prose and its
    # <h1>-<h6> headings rather than on its tags.
    html_headings = 0
    if looks_like_html(text):
        text, html_headings = html_to_text(text)

    body     = text
    haystack = f"{name}\n{text}" if name else text
    feat     = _structural_features(text, html_headings=html_headings)

    raw     = {}
    matched = {}
    for dtype, rules in _DOC_TYPE_RX.items():
        if dtype == "DUMP":
            continue
        total, hits = 0.0, []
        for rx, weight, label in rules:
            n = len(rx.findall(haystack if weight >= _NAME_VOTE_MIN_WEIGHT else body))
            if n:
                # Repeats corroborate but must not let one keyword dominate:
                # the second hit counts half, everything beyond that is capped.
                factor = 1.0 + min(0.5, (n - 1) * 0.25)
                total += weight * factor
                hits.append({"signal": label, "count": n, "weight": weight})
        if total:
            raw[dtype]     = total
            matched[dtype] = sorted(hits, key=lambda h: -h["weight"] * h["count"])

    scores = {t: round(min(1.0, raw.get(t, 0.0) / DOC_TYPE_NORM[t]), 3)
              for t in DOC_TYPES if t != "DUMP"}

    best_other     = max(scores.values()) if scores else 0.0
    scores["DUMP"] = round(min(1.0, _dump_score(feat, best_other) / DOC_TYPE_NORM["DUMP"]), 3)

    top       = max(DOC_TYPES, key=lambda t: (scores[t], -_TYPE_PRIORITY.index(t)))
    ranked    = sorted(scores.values(), reverse=True)
    runner_up = ranked[1] if len(ranked) > 1 else 0.0

    # Confidence is strength AND separation: a document scoring 0.8 on two
    # types at once is not confidently either one.
    margin     = scores[top] - runner_up
    confidence = round(min(0.99, scores[top] * (0.65 + 0.35 * min(1.0, margin / 0.35))), 3)

    if scores[top] == 0.0:
        # Nothing fired. Short files are dumps; long ones are real documents
        # this classifier simply has no signature for, and saying so is the
        # honest output.
        top        = "DUMP" if feat["words"] <= DUMP_MAX_WORDS else "UNCLASSIFIED"
        confidence = 0.1

    runner_name = max((t for t in DOC_TYPES if t != top), key=lambda t: scores[t])

    return {
        "doc_type":        top,
        "type_confidence": confidence,
        "type_scores":     scores,
        "type_runner_up":  runner_name,
        "type_evidence":   matched.get(top, [])[:6],
        "structure":       feat,
    }


def classify_file(path: str, sample_text: str = "", folder_class: str = "") -> dict:
    """
    Full 5-tag + 12-variable master equation classification. Always runs.
    Called on every create, modify, and move event — not optional.

    Five non-negotiable tags:
        1. domain       — knowledge domain (physics/theology/code/…)
        2. chi_factor   — dominant CHI variable (G/M/E/S/T/K/R/Q/F/C)
        3. law          — dominant law mapping (L01–L10)
        4. content_type — what the file IS (code/document/data/note/image/…)
        5. evidence     — empirical density 0–100%  (+ fruit/anti_fruit bonus)
    """
    p = Path(path)
    ext = p.suffix.lower()

    if not sample_text:
        sample_text = _read_sample(path)

    is_blob = not sample_text and ext not in {
        ".txt",".md",".py",".js",".ts",".json",".yaml",".yml",".csv",
        ".html",".htm",".xml",".ini",".cfg",".bat",".ps1",".sh",".ahk",
        ".log",".rst",".toml",".sql",".css",".scss",
    }

    # ── 12-variable CHI master equation ──────────────────────────────────────
    chi     = {k: score_chi_factor(sample_text, k) for k in CHI_SIGNALS}
    chi_sum = sum(chi.values())

    domain_name, domain_score = score_domain(sample_text)
    law_name,    law_score    = score_law(sample_text)

    dominant_chi = max(chi, key=lambda k: (chi[k], k)) if chi_sum > 0 else "none"

    nonzero      = sum(1 for v in chi.values() if v > 0)
    max_possible = 10 * 3 + 3 + 3
    raw_conf     = (chi_sum + domain_score + law_score) / max_possible
    spread_bonus = min(0.15, nonzero * 0.02)
    confidence   = min(0.99, raw_conf + spread_bonus)

    chi_name = CHI_SIGNALS[dominant_chi]["name"] if dominant_chi != "none" else "unclassified"
    role     = f"{chi_name.lower().replace(' ','_')}_{_role_from_ext(ext)}"

    # ── Tag 4: content type ───────────────────────────────────────────────────
    if is_blob:
        content_type = _role_from_ext(ext)   # image / video / audio / file
    else:
        content_type = detect_content_type(ext, sample_text)

    # ── Tag 5: evidence density + fruit signal ───────────────────────────────
    evidence   = score_evidence(sample_text)
    fruit      = score_fruit(sample_text)
    anti_fruit = score_anti_fruit(sample_text)

    # -- Second axis: document TYPE (orthogonal to the CHI "about" axis) ------
    if is_blob:
        # Binaries have no document structure to read; typing them would be
        # invention, so they are left explicitly untyped rather than guessed.
        dtype = {
            "doc_type": "UNTYPED", "type_confidence": 0.0, "type_scores": {},
            "type_runner_up": None, "type_evidence": [], "structure": {},
        }
    else:
        dtype = classify_document_type(sample_text, name=p.name, path=str(p))

    # -- Lossless address (naming grammar; does not rename or move anything) --
    try:
        from fis_namer import propose_lossless_address
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        lossless = propose_lossless_address(p.stem, sample_text, mtime)
        lossless_address = lossless["address"]
    except Exception:
        # The namer is optional here: a classification must never fail because
        # addressing failed.
        lossless, lossless_address = {}, None

    safe_actions = _safe_actions_for(folder_class, confidence, dominant_chi)

    return {
        # 5 non-negotiable tags
        "domain":        {"name": domain_name,  "score": domain_score},
        "chi_factor":    dominant_chi,
        "law":           {"name": law_name,     "score": law_score},
        "content_type":  content_type,
        "evidence":      evidence,
        "structural_evidence": score_structural_evidence(sample_text) if score_structural_evidence and not is_blob else {},
        # second axis: document type
        "doc_type":        dtype["doc_type"],
        "type_confidence": dtype["type_confidence"],
        "type_scores":     dtype["type_scores"],
        "type_runner_up":  dtype["type_runner_up"],
        "type_evidence":   dtype["type_evidence"],
        "structure":       dtype["structure"],
        # lossless addressing
        "lossless_address":        lossless_address,
        "lossless_address_detail": lossless,
        # full CHI vector
        "chi":           chi,
        "chi_name":      chi_name,
        "chi_sum":       chi_sum,
        "confidence":    round(confidence, 3),
        "file_role":     role,
        "ext":           ext,
        "fruit":         fruit,
        "anti_fruit":    anti_fruit,
        "safe_actions":  safe_actions,
        "needs_ai_fallback": confidence < FALLBACK_THRESHOLD,
        "folder_class":     folder_class,
    }


def _read_sample(path: str, max_bytes: int = 6000) -> str:
    """Read a small text sample from a file for classification."""
    p   = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in {".txt",".md",".rst",".log",".csv",".ahk",".py",".js",
                   ".ts",".html",".htm",".json",".yaml",".yml",".ini",
                   ".cfg",".bat",".ps1",".sql",".sh"}:
            return p.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
                pages = PdfReader(str(p)).pages[:3]
                return "\n".join((pg.extract_text() or "") for pg in pages)[:max_bytes]
            except Exception:
                return ""
        if ext in {".docx"}:
            try:
                import docx
                doc = docx.Document(str(p))
                return "\n".join(para.text for para in doc.paragraphs)[:max_bytes]
            except Exception:
                return ""
    except Exception:
        pass
    # For blobs (images, video, audio) use filename + ext as sample
    return f"{p.stem} {p.suffix}"


def _role_from_ext(ext: str) -> str:
    if ext in MEDIA_EXTS:  return "media"
    if ext in DOC_EXTS:    return "document"
    if ext in CODE_EXTS:   return "code"
    if ext in TEXT_EXTS:   return "text"
    return "file"


def _safe_actions_for(folder_class: str, confidence: float, dominant_chi: str) -> list:
    if folder_class == FolderClass.SYSTEM:
        return ["index", "hash"]
    if confidence < 0.3:
        return ["index", "hash", "flag_review"]
    if confidence < FALLBACK_THRESHOLD:
        return ["index", "hash", "flag_review", "propose_name"]
    base = ["index", "hash", "propose_name"]
    if confidence >= 0.65:
        base.append("rename")
    if confidence >= 0.80:
        base.append("move")
    return base


# ---------------------------------------------------------------------------
# AI fallback  (called when local confidence < FALLBACK_THRESHOLD)
# ---------------------------------------------------------------------------

def ai_classify(path: str, sample_text: str, local_result: dict) -> dict:
    """
    Call Claude API to classify a file the local engine isn't confident about.
    Returns a dict with the same shape as classify_file(), merging AI answers in.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        local_result["ai_fallback_skipped"] = "no ANTHROPIC_API_KEY"
        return local_result

    try:
        import urllib.request
        prompt = _build_ai_prompt(path, sample_text, local_result)
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",   # fast + cheap for classification
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        raw = data["content"][0]["text"].strip()
        # strip markdown code fence if present
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw).rstrip("`").strip()
        ai = json.loads(raw)
        local_result.update({
            "ai_domain":       ai.get("domain", local_result["domain"]["name"]),
            "ai_role":         ai.get("file_role", local_result["file_role"]),
            "ai_confidence":   ai.get("confidence", 0.5),
            "ai_safe_actions": ai.get("safe_actions", []),
            "ai_notes":        ai.get("notes", ""),
            "needs_ai_fallback": False,
        })
        # boost confidence with AI result
        local_result["confidence"] = round(
            max(local_result["confidence"], ai.get("confidence", 0.5)), 3
        )
    except Exception as e:
        local_result["ai_fallback_error"] = str(e)

    return local_result


def _build_ai_prompt(path: str, sample: str, local: dict) -> str:
    name    = Path(path).name
    preview = sample[:800].replace("\n", " ")
    chi     = local.get("chi", {})
    return f"""Classify this file for the FIS (File Intelligence System).

File: {name}
Sample content (first 800 chars): {preview}
Local CHI scores (0-3): {json.dumps(chi)}

Return ONLY valid JSON, no markdown, no explanation:
{{
  "domain": "one of: physics|theology|epistemology|morality|consciousness|information|code|media|document|data|unknown",
  "file_role": "short snake_case description, e.g. research_document or invoice or code_module",
  "confidence": 0.0-1.0,
  "safe_actions": ["index","rename","move","archive"],
  "notes": "one sentence about what this file appears to be"
}}"""


# ---------------------------------------------------------------------------
# Convenience: classify a path (auto-detect file vs folder)
# ---------------------------------------------------------------------------

def classify(path: str, folder_class: str = "") -> dict:
    """Entry point: classify either a file or a folder."""
    p = Path(path)
    if p.is_dir():
        result         = classify_folder(path)
        result["path"] = path
        return result
    else:
        result           = classify_file(path, folder_class=folder_class)
        result["path"]   = path
        if result.get("needs_ai_fallback"):
            sample = _read_sample(path)
            result = ai_classify(path, sample, result)
        return result


# ---------------------------------------------------------------------------
# CLI  (python fis_classifier.py <path>)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, pprint
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    result = classify(path)
    pprint.pprint(result, sort_dicts=False)

