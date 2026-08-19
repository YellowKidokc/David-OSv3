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

def _score_terms(text: str, terms: set, cap: int = 8) -> float:
    """Return 0-100 score of how many terms from the set appear in text."""
    low  = text.lower()
    hits = sum(1 for t in terms if t in low)
    return round(min(100.0, (hits / cap) * 100.0), 1)

def score_evidence(text: str) -> float:
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

    safe_actions = _safe_actions_for(folder_class, confidence, dominant_chi)

    return {
        # 5 non-negotiable tags
        "domain":        {"name": domain_name,  "score": domain_score},
        "chi_factor":    dominant_chi,
        "law":           {"name": law_name,     "score": law_score},
        "content_type":  content_type,
        "evidence":      evidence,
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
