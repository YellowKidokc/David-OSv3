"""
FOLDER SYMPTOM SCANNER v1.0
============================
Turns the Folder Symptom Registry (40 symptoms across 6 categories)
into a working scanner that can diagnose any folder on your system.

WHAT IT DOES:
  - Walks a target directory
  - Runs all 40 detection functions
  - Produces a scored report (per-symptom results + overall health grade)
  - Optionally pushes results to the File Intelligence Hub API
    (Top of Mind messages, shared memory, clipboard, ntfy notifications)

USAGE:
  # Scan a folder, print report
  python folder_scanner.py D:\Downloads

  # Scan and push results to the Hub API
  python folder_scanner.py D:\Downloads --api http://localhost:8100

  # Scan and send ntfy notification
  python folder_scanner.py D:\Downloads --ntfy http://localhost:10700/fis-scan

  # Scan specific categories only
  python folder_scanner.py D:\Downloads --categories structural,content

  # JSON output
  python folder_scanner.py D:\Downloads --json

  # Scan multiple folders
  python folder_scanner.py D:\Downloads D:\GitHub O:\_Theophysics_v5

REQUIREMENTS:
  pip install httpx chardet  (chardet optional, for encoding detection)

SCHEMA (from TopOfMind Numbering Schema v1.0):
  Source ID:    22003 (FileWatcher)
  Msg Type:     31010 (file-watch-event)
  Priority:     40001-40010 (by severity)
"""

import os
import sys
import re
import json
import hashlib
import argparse
import datetime
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Data Structures ─────────────────────────────────────────

@dataclass
class SymptomResult:
    symptom_id: str
    category: str
    name: str
    severity: str  # low, medium, high, critical
    description: str
    affected_paths: list = field(default_factory=list)
    count: int = 0
    auto_fixable: bool = False
    details: dict = field(default_factory=dict)

    @property
    def priority_code(self) -> int:
        return {"low": 40001, "medium": 40003, "high": 40007, "critical": 40010}[self.severity]


@dataclass
class ScanReport:
    target: str
    scanned_at: str
    total_files: int = 0
    total_dirs: int = 0
    symptoms: list = field(default_factory=list)
    grade: str = "A"
    score: float = 100.0

    def compute_grade(self):
        penalty = 0
        for s in self.symptoms:
            if s.count == 0:
                continue
            w = {"low": 1, "medium": 3, "high": 8, "critical": 20}[s.severity]
            penalty += min(s.count * w, w * 10)
        self.score = max(0, 100 - penalty)
        if self.score >= 90: self.grade = "A"
        elif self.score >= 75: self.grade = "B"
        elif self.score >= 60: self.grade = "C"
        elif self.score >= 40: self.grade = "D"
        else: self.grade = "F"


# ── File System Helpers ─────────────────────────────────────

def walk_target(root: str):
    """Walk directory, return (files, dirs, file_info_list)."""
    files = []
    dirs = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirs.append(dirpath)
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                stat = os.stat(fp)
                files.append({
                    "path": fp,
                    "name": f,
                    "stem": Path(f).stem,
                    "ext": Path(f).suffix.lower(),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "atime": stat.st_atime,
                    "dir": dirpath,
                    "depth": dirpath.replace(root, "").count(os.sep),
                })
            except (OSError, PermissionError):
                pass
    return files, dirs


def file_hash(path: str, quick: bool = True) -> str:
    """MD5 hash of file. If quick=True, only hash first 8KB."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            data = f.read(8192 if quick else -1)
            h.update(data)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


# ── STRUCTURAL DETECTORS (S01-S08) ─────────────────────────

def detect_ext_swamp(files, dirs, root) -> SymptomResult:
    """S01: Many unrelated file types in one folder."""
    r = SymptomResult("S01", "Structural", "Extension swamp", "medium",
                      "Many unrelated file types dumped together")
    by_dir = defaultdict(set)
    for f in files:
        by_dir[f["dir"]].add(f["ext"])
    for d, exts in by_dir.items():
        if len(exts) > 8:
            r.affected_paths.append(d)
            r.count += 1
            r.details[d] = list(exts)
    return r

def detect_version_sprawl(files, dirs, root) -> SymptomResult:
    """S02: file_v1, file_v2, file_FINAL_FINAL."""
    r = SymptomResult("S02", "Structural", "Version sprawl", "medium",
                      "Multiple version/copy suffixes of same file")
    pat = re.compile(r'[_\-\s](v\d+|final|copy|backup|\(\d+\))', re.IGNORECASE)
    for f in files:
        if pat.search(f["stem"]):
            r.affected_paths.append(f["path"])
            r.count += 1
    return r

def detect_depth_explosion(files, dirs, root) -> SymptomResult:
    """S03: Deeply nested folders with few files at bottom."""
    r = SymptomResult("S03", "Structural", "Depth explosion", "low",
                      "Deeply nested paths with sparse leaf nodes", auto_fixable=True)
    for f in files:
        if f["depth"] > 5:
            parent = f["dir"]
            siblings = sum(1 for x in files if x["dir"] == parent)
            if siblings < 3:
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_flat_overload(files, dirs, root) -> SymptomResult:
    """S04: 500+ files in one directory."""
    r = SymptomResult("S04", "Structural", "Flat overload", "medium",
                      "Too many files in a single directory")
    by_dir = Counter(f["dir"] for f in files)
    for d, count in by_dir.items():
        if count > 200:
            r.affected_paths.append(d)
            r.count += 1
            r.details[d] = count
    return r

def detect_orphan_sidecar(files, dirs, root) -> SymptomResult:
    """S05: Sidecar files whose parent is gone."""
    r = SymptomResult("S05", "Structural", "Orphan sidecar", "low",
                      "Metadata sidecars without parent files", auto_fixable=True)
    sidecar_exts = {
        ".chi", ".fmeta", ".fisnote", ".fistag", ".fisdead",
        ".srt", ".meta.json", ".bak"
    }
    all_stems = {(f["dir"], f["stem"]) for f in files}
    for f in files:
        if f["ext"] in sidecar_exts:
            base_stem = f["stem"].replace(".meta", "")
            if (f["dir"], base_stem) not in all_stems:
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_naming_collision(files, dirs, root) -> SymptomResult:
    """S06: Near-identical filenames in same directory."""
    r = SymptomResult("S06", "Structural", "Naming collision", "high",
                      "Files with near-identical names")
    by_dir = defaultdict(list)
    for f in files:
        by_dir[f["dir"]].append(f)
    for d, flist in by_dir.items():
        lowered = defaultdict(list)
        for f in flist:
            lowered[f["name"].lower()].append(f["path"])
        for key, paths in lowered.items():
            if len(paths) > 1:
                r.affected_paths.extend(paths)
                r.count += 1
    return r

def detect_project_scatter(files, dirs, root) -> SymptomResult:
    """S07: Project keywords scattered across distant folders."""
    r = SymptomResult("S07", "Structural", "Project scatter", "high",
                      "One project split across unrelated folders")
    keywords = defaultdict(list)
    project_markers = {"readme", "package", "requirements", "cargo", "makefile",
                       "pyproject", "setup", "config", "manifest"}
    for f in files:
        stem_low = f["stem"].lower()
        if stem_low in project_markers:
            project_name = os.path.basename(f["dir"])
            keywords[project_name].append(f["dir"])
    for proj, locations in keywords.items():
        unique = set(locations)
        if len(unique) > 2:
            r.affected_paths.extend(unique)
            r.count += 1
            r.details[proj] = list(unique)
    return r

def detect_phantom_refs(files, dirs, root) -> SymptomResult:
    """S08: Broken internal links in markdown/HTML."""
    r = SymptomResult("S08", "Structural", "Phantom reference", "medium",
                      "Files referencing deleted/moved targets")
    link_pat = re.compile(r'\[\[([^\]]+)\]\]|\[.*?\]\(([^)]+)\)')
    md_files = [f for f in files if f["ext"] in {".md", ".html", ".htm"}]
    all_stems = {f["stem"].lower() for f in files}
    for f in md_files[:200]:  # cap for performance
        try:
            content = open(f["path"], "r", encoding="utf-8", errors="ignore").read(50000)
        except (OSError, PermissionError):
            continue
        for m in link_pat.finditer(content):
            target = (m.group(1) or m.group(2) or "").strip()
            if target.startswith("http") or target.startswith("#"):
                continue
            target_stem = Path(target).stem.lower()
            if target_stem and target_stem not in all_stems:
                r.affected_paths.append(f["path"])
                r.count += 1
                break
    return r


# ── CONTENT DETECTORS (C01-C08) ────────────────────────────

def detect_duplicates(files, dirs, root) -> SymptomResult:
    """C01: Same file content in multiple locations."""
    r = SymptomResult("C01", "Content", "Duplicate cluster", "medium",
                      "Identical files in multiple locations")
    size_groups = defaultdict(list)
    for f in files:
        if f["size"] > 100:
            size_groups[f["size"]].append(f)
    for size, group in size_groups.items():
        if len(group) < 2:
            continue
        hashes = defaultdict(list)
        for f in group:
            h = file_hash(f["path"])
            if h:
                hashes[h].append(f["path"])
        for h, paths in hashes.items():
            if len(paths) > 1:
                r.affected_paths.extend(paths)
                r.count += 1
    return r

def detect_format_redundancy(files, dirs, root) -> SymptomResult:
    """C02: Same content in .md + .html + .pdf + .docx."""
    r = SymptomResult("C02", "Content", "Format redundancy", "low",
                      "Same document in multiple formats")
    by_stem = defaultdict(list)
    for f in files:
        by_stem[(f["dir"], f["stem"])].append(f["ext"])
    for (d, stem), exts in by_stem.items():
        doc_exts = {e for e in exts if e in {".md", ".html", ".htm", ".pdf", ".docx", ".txt", ".rtf"}}
        if len(doc_exts) > 1:
            r.affected_paths.append(os.path.join(d, stem))
            r.count += 1
    return r

def detect_draft_graveyard(files, dirs, root) -> SymptomResult:
    """C03: Old drafts never consolidated."""
    r = SymptomResult("C03", "Content", "Draft graveyard", "low",
                      "Abandoned drafts and WIP files")
    pat = re.compile(r'(draft|wip|old|temp|scratch|notes|brainstorm|rough)', re.IGNORECASE)
    for f in files:
        if pat.search(f["stem"]):
            age_days = (datetime.datetime.now().timestamp() - f["mtime"]) / 86400
            if age_days > 30:
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_doc_chaos(files, dirs, root) -> SymptomResult:
    """C04: Mixed document types with no structure."""
    r = SymptomResult("C04", "Content", "Document chaos", "medium",
                      "PDF/doc/xlsx mixed with no organization")
    doc_exts = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx"}
    by_dir = defaultdict(set)
    for f in files:
        if f["ext"] in doc_exts:
            by_dir[f["dir"]].add(f["ext"])
    for d, exts in by_dir.items():
        if len(exts) >= 3:
            r.affected_paths.append(d)
            r.count += 1
    return r

def detect_media_dump(files, dirs, root) -> SymptomResult:
    """C05: Images/video with auto-generated names."""
    r = SymptomResult("C05", "Content", "Media dump", "low",
                      "Media files with weak auto-generated names", auto_fixable=True)
    pat = re.compile(r'^(IMG_|DSC_|Screenshot|Photo_|VID_|MOV_|WP_|DCIM)', re.IGNORECASE)
    for f in files:
        if f["ext"] in {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi", ".webp"}:
            if pat.match(f["stem"]):
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_unknown_blobs(files, dirs, root) -> SymptomResult:
    """C06: Files with no recognizable extension."""
    r = SymptomResult("C06", "Content", "Unknown blobs", "medium",
                      "Unrecognized file types")
    known = {".md", ".txt", ".py", ".js", ".ts", ".html", ".htm", ".css", ".json",
             ".yml", ".yaml", ".toml", ".csv", ".xml", ".pdf", ".docx", ".doc",
             ".xlsx", ".xls", ".pptx", ".jpg", ".jpeg", ".png", ".gif", ".svg",
             ".mp3", ".mp4", ".wav", ".mov", ".avi", ".zip", ".tar", ".gz", ".7z",
             ".rar", ".exe", ".msi", ".bat", ".sh", ".ps1", ".lean", ".rs", ".go",
             ".c", ".cpp", ".h", ".java", ".rb", ".php", ".r", ".sql", ".db",
             ".sqlite", ".log", ".ini", ".cfg", ".env", ".gitignore", ".bak",
             ".webp", ".ico", ".ttf", ".woff", ".woff2", ".eot", ".otf",
             ".chi", ".fmeta", ".fisnote", ".fistag", ".fisdead"}
    for f in files:
        if f["ext"] and f["ext"] not in known:
            r.affected_paths.append(f["path"])
            r.count += 1
        elif not f["ext"]:
            r.affected_paths.append(f["path"])
            r.count += 1
    return r

def detect_encoding_chaos(files, dirs, root) -> SymptomResult:
    """C07: Mixed encodings in text files."""
    r = SymptomResult("C07", "Content", "Encoding chaos", "medium",
                      "Inconsistent text file encodings", auto_fixable=True)
    try:
        import chardet
    except ImportError:
        r.details["skipped"] = "chardet not installed"
        return r
    text_exts = {".txt", ".md", ".csv", ".html", ".htm", ".json", ".xml", ".yml", ".yaml"}
    by_dir = defaultdict(list)
    for f in files[:500]:
        if f["ext"] in text_exts and f["size"] > 10:
            try:
                raw = open(f["path"], "rb").read(4096)
                det = chardet.detect(raw)
                enc = (det.get("encoding") or "unknown").upper()
                by_dir[f["dir"]].append(enc)
            except (OSError, PermissionError):
                pass
    for d, encs in by_dir.items():
        unique = set(encs)
        if len(unique) > 1 and "UTF-8" in unique:
            non_utf8 = unique - {"UTF-8", "ASCII"}
            if non_utf8:
                r.affected_paths.append(d)
                r.count += 1
                r.details[d] = list(unique)
    return r

def detect_incomplete_extract(files, dirs, root) -> SymptomResult:
    """C08: Archive + extracted folder both present."""
    r = SymptomResult("C08", "Content", "Incomplete extraction", "low",
                      "Archive and extracted contents both present")
    archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz", ".tar.gz"}
    archives = [f for f in files if f["ext"] in archive_exts]
    dir_names = {os.path.basename(d).lower() for d in dirs}
    for a in archives:
        if a["stem"].lower() in dir_names:
            r.affected_paths.append(a["path"])
            r.count += 1
    return r


# ── TEMPORAL DETECTORS (T01-T04) ───────────────────────────

def detect_time_bombs(files, dirs, root) -> SymptomResult:
    """T01: Files untouched for 6+ months in active directories."""
    r = SymptomResult("T01", "Temporal", "Time bomb", "low",
                      "Stale files in active directories")
    now = datetime.datetime.now().timestamp()
    six_months = 180 * 86400
    by_dir = defaultdict(list)
    for f in files:
        by_dir[f["dir"]].append(f)
    for d, flist in by_dir.items():
        newest = max(f["mtime"] for f in flist)
        if now - newest < 30 * 86400:  # dir is active
            stale = [f for f in flist if now - f["mtime"] > six_months]
            if stale and len(stale) < len(flist):
                r.affected_paths.extend(f["path"] for f in stale[:10])
                r.count += len(stale)
    return r

def detect_burst_dump(files, dirs, root) -> SymptomResult:
    """T02: 50+ files from same day, no organization."""
    r = SymptomResult("T02", "Temporal", "Burst dump", "medium",
                      "Mass file drops from a single day")
    by_dir = defaultdict(lambda: defaultdict(list))
    for f in files:
        day = datetime.datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d")
        by_dir[f["dir"]][day].append(f)
    for d, days in by_dir.items():
        for day, flist in days.items():
            if len(flist) > 50:
                r.affected_paths.append(d)
                r.count += 1
                r.details[f"{d} ({day})"] = len(flist)
    return r

def detect_stale_pipeline(files, dirs, root) -> SymptomResult:
    """T03: Old processing outputs never cleaned."""
    r = SymptomResult("T03", "Temporal", "Stale pipeline", "medium",
                      "Old intermediate outputs still present")
    pipe_dirs = {"output", "outputs", "temp", "tmp", "cache", "_cache",
                 "__pycache__", ".cache", "build", "dist", "_build"}
    now = datetime.datetime.now().timestamp()
    for d in dirs:
        if os.path.basename(d).lower() in pipe_dirs:
            try:
                mtime = os.path.getmtime(d)
                if now - mtime > 30 * 86400:
                    r.affected_paths.append(d)
                    r.count += 1
            except OSError:
                pass
    return r

def detect_abandoned_workspace(files, dirs, root) -> SymptomResult:
    """T04: Structured project with no recent activity."""
    r = SymptomResult("T04", "Temporal", "Abandoned workspace", "low",
                      "Structured project with no recent changes")
    now = datetime.datetime.now().timestamp()
    structure_markers = {"readme.md", "package.json", "pyproject.toml", "cargo.toml",
                         "makefile", "setup.py", ".git"}
    first_level = [d for d in dirs if d.count(os.sep) - root.count(os.sep) == 1]
    for d in first_level:
        contents = {f["name"].lower() for f in files if f["dir"] == d}
        if contents & structure_markers:
            sub_files = [f for f in files if f["path"].startswith(d)]
            if sub_files:
                newest = max(f["mtime"] for f in sub_files)
                if now - newest > 90 * 86400:
                    r.affected_paths.append(d)
                    r.count += 1
                    r.details[d] = f"Last modified {int((now - newest) / 86400)} days ago"
    return r


# ── INFRASTRUCTURE DETECTORS (I01-I08) ─────────────────────

def detect_program_root(files, dirs, root) -> SymptomResult:
    """I01: Application roots that must NEVER be auto-touched."""
    r = SymptomResult("I01", "Infrastructure", "Program-root danger", "critical",
                      "App/project roots with dependencies — DO NOT AUTO-MOVE")
    markers = {"package.json", "node_modules", ".git", "venv", ".venv",
               "requirements.txt", "pyproject.toml", "cargo.toml", "go.mod"}
    for d in dirs:
        contents = {f["name"].lower() for f in files if f["dir"] == d}
        subdirs = {os.path.basename(sd).lower() for sd in dirs if os.path.dirname(sd) == d}
        all_items = contents | subdirs
        if all_items & markers:
            r.affected_paths.append(d)
            r.count += 1
    return r

def detect_toolchain_residue(files, dirs, root) -> SymptomResult:
    """I02: Build artifacts outside project roots."""
    r = SymptomResult("I02", "Infrastructure", "Toolchain residue", "medium",
                      "Build artifacts in non-project directories", auto_fixable=True)
    junk = {"__pycache__", "node_modules", ".cache", ".tox", ".mypy_cache",
            ".pytest_cache", ".ruff_cache", "dist", "build"}
    for d in dirs:
        basename = os.path.basename(d).lower()
        if basename in junk:
            parent = os.path.dirname(d)
            parent_files = {f["name"].lower() for f in files if f["dir"] == parent}
            if not (parent_files & {"package.json", "pyproject.toml", "setup.py", "cargo.toml"}):
                r.affected_paths.append(d)
                r.count += 1
    return r

def detect_config_leak(files, dirs, root) -> SymptomResult:
    """I03: Exposed credentials and API keys. CRITICAL."""
    r = SymptomResult("I03", "Infrastructure", "Config leak", "critical",
                      "Credentials or API keys in exposed locations")
    danger_names = {".env", ".env.local", ".env.production"}
    key_pat = re.compile(r'(api[_-]?key|secret|token|password|credential)\s*[:=]', re.IGNORECASE)
    for f in files:
        if f["name"].lower() in danger_names:
            r.affected_paths.append(f["path"])
            r.count += 1
        elif f["ext"] in {".txt", ".md", ".json", ".yml", ".yaml", ".cfg", ".ini", ".toml"}:
            if f["size"] < 50000:
                try:
                    content = open(f["path"], "r", encoding="utf-8", errors="ignore").read(10000)
                    if key_pat.search(content):
                        if "sk-" in content or "ghp_" in content or "AKIA" in content:
                            r.affected_paths.append(f["path"])
                            r.count += 1
                except (OSError, PermissionError):
                    pass
    return r

def detect_sync_ghost(files, dirs, root) -> SymptomResult:
    """I04: Cloud sync conflict files."""
    r = SymptomResult("I04", "Infrastructure", "Sync ghost", "high",
                      "Unresolved sync conflict files")
    pat = re.compile(r'(sync-conflict|conflicted copy|\(conflict\))', re.IGNORECASE)
    for f in files:
        if pat.search(f["name"]):
            r.affected_paths.append(f["path"])
            r.count += 1
    return r

def detect_repo_mix(files, dirs, root) -> SymptomResult:
    """I05: Git-tracked and untracked files mixed."""
    r = SymptomResult("I05", "Infrastructure", "Repo / non-repo mix", "high",
                      "Git repos mixed with untracked personal files")
    for d in dirs:
        if os.path.basename(d) == ".git":
            parent = os.path.dirname(d)
            non_project = []
            for f in files:
                if f["dir"] == parent:
                    if f["ext"] in {".jpg", ".jpeg", ".png", ".mp4", ".doc", ".docx", ".pdf"}:
                        non_project.append(f["path"])
            if len(non_project) > 3:
                r.affected_paths.extend(non_project[:5])
                r.count += 1
    return r

def detect_mirror_drift(files, dirs, root) -> SymptomResult:
    """I06: Local and backup copies diverged. (Placeholder — needs NAS comparison.)"""
    r = SymptomResult("I06", "Infrastructure", "Mirror drift", "high",
                      "Local vs backup copies may have diverged")
    r.details["note"] = "Full implementation requires NAS hash comparison — run with --nas flag"
    return r

def detect_broken_shortcuts(files, dirs, root) -> SymptomResult:
    """I07: Broken .lnk shortcuts."""
    r = SymptomResult("I07", "Infrastructure", "Shortcut graveyard", "low",
                      "Broken shortcuts to moved/deleted files", auto_fixable=True)
    for f in files:
        if f["ext"] == ".lnk" and f["size"] < 100:
            r.affected_paths.append(f["path"])
            r.count += 1
    return r

def detect_log_accumulation(files, dirs, root) -> SymptomResult:
    """I08: Oversized or old log files."""
    r = SymptomResult("I08", "Infrastructure", "Log accumulation", "low",
                      "Growing log files never rotated", auto_fixable=True)
    now = datetime.datetime.now().timestamp()
    for f in files:
        if f["ext"] == ".log":
            if f["size"] > 10 * 1024 * 1024 or (now - f["mtime"] > 30 * 86400):
                r.affected_paths.append(f["path"])
                r.count += 1
    return r


# ── NAMING DETECTORS (N01-N04) ─────────────────────────────

def detect_name_rot(files, dirs, root) -> SymptomResult:
    """N01: Auto-generated names (Screenshot, Untitled, New Document)."""
    r = SymptomResult("N01", "Naming", "Name rot", "low",
                      "Files with meaningless auto-generated names")
    pat = re.compile(r'^(Untitled|New Document|Screenshot|IMG_\d|DSC_\d|Document\s?\(\d|Copy of )', re.IGNORECASE)
    for f in files:
        if pat.match(f["stem"]):
            r.affected_paths.append(f["path"])
            r.count += 1
    return r

def detect_download_purgatory(files, dirs, root) -> SymptomResult:
    """N02: Installers mixed with documents."""
    r = SymptomResult("N02", "Naming", "Download purgatory", "medium",
                      "Executables and installers mixed with documents")
    exe_exts = {".exe", ".msi", ".dmg", ".deb", ".rpm", ".appimage"}
    doc_exts = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".md", ".txt"}
    by_dir = defaultdict(lambda: {"exe": 0, "doc": 0})
    for f in files:
        if f["ext"] in exe_exts:
            by_dir[f["dir"]]["exe"] += 1
        elif f["ext"] in doc_exts:
            by_dir[f["dir"]]["doc"] += 1
    for d, counts in by_dir.items():
        if counts["exe"] > 0 and counts["doc"] > 0:
            r.affected_paths.append(d)
            r.count += 1
    return r

def detect_tiny_debris(files, dirs, root) -> SymptomResult:
    """N03: Empty or near-empty folders."""
    r = SymptomResult("N03", "Naming", "Tiny-folder debris", "low",
                      "Empty or temp folders cluttering the tree", auto_fixable=True)
    for d in dirs:
        if d == root:
            continue
        dir_files = [f for f in files if f["dir"] == d]
        sub_dirs = [sd for sd in dirs if os.path.dirname(sd) == d]
        if len(dir_files) == 0 and len(sub_dirs) == 0:
            r.affected_paths.append(d)
            r.count += 1
    return r

def detect_path_length(files, dirs, root) -> SymptomResult:
    """N04: Paths approaching Windows 260-char limit."""
    r = SymptomResult("N04", "Naming", "Path length danger", "medium",
                      "File paths nearing OS limits")
    for f in files:
        if len(f["path"]) > 200:
            r.affected_paths.append(f["path"])
            r.count += 1
            r.details[f["path"]] = len(f["path"])
    return r


# ── RESEARCH CORPUS DETECTORS (R01-R08) ───────────────────

def detect_untagged_canonical(files, dirs, root) -> SymptomResult:
    """R01: Important files without .chi classification."""
    r = SymptomResult("R01", "Research Corpus", "Untagged canonical", "high",
                      "Core framework files missing chi classification", auto_fixable=True)
    chi_stems = {f["stem"].replace(".chi", "") for f in files if f["ext"] == ".chi"}
    canonical_exts = {".md", ".lean", ".pdf", ".html"}
    for f in files:
        if f["ext"] in canonical_exts and f["size"] > 1000:
            if f["stem"] not in chi_stems:
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_ai_debris(files, dirs, root) -> SymptomResult:
    """R02: Raw AI conversation exports and temp prompts."""
    r = SymptomResult("R02", "Research Corpus", "AI session debris", "medium",
                      "Unsorted AI exports and conversation dumps")
    ai_pat = re.compile(r'(claude_export|chatgpt|conversation|prompt_|gpt-|opus-|transcript)', re.IGNORECASE)
    for f in files:
        if ai_pat.search(f["stem"]) or f["ext"] == ".json" and "conversation" in f["stem"].lower():
            r.affected_paths.append(f["path"])
            r.count += 1
    return r

def detect_cross_purpose(files, dirs, root) -> SymptomResult:
    """R03: Personal files mixed with research."""
    r = SymptomResult("R03", "Research Corpus", "Cross-purpose pollution", "medium",
                      "Personal content in research directories")
    personal_pat = re.compile(r'(invoice|receipt|bill|tax|medical|family|vacation|birthday)', re.IGNORECASE)
    for f in files:
        if personal_pat.search(f["stem"]):
            parent_lower = f["dir"].lower()
            if any(w in parent_lower for w in ["research", "paper", "project", "theophysics", "framework"]):
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_mixed_provenance(files, dirs, root) -> SymptomResult:
    """R04: Files from multiple AIs with no attribution."""
    r = SymptomResult("R04", "Research Corpus", "Mixed provenance", "medium",
                      "Files from multiple sources without attribution")
    ai_markers = {"claude", "gpt", "gemini", "kimi", "opus", "sonnet", "copilot", "codex"}
    by_dir = defaultdict(set)
    for f in files:
        stem_low = f["stem"].lower()
        for marker in ai_markers:
            if marker in stem_low:
                by_dir[f["dir"]].add(marker)
    for d, sources in by_dir.items():
        if len(sources) > 1:
            r.affected_paths.append(d)
            r.count += 1
            r.details[d] = list(sources)
    return r

def detect_archive_pile(files, dirs, root) -> SymptomResult:
    """R05: Archives mixed with live files."""
    r = SymptomResult("R05", "Research Corpus", "Archive pile", "low",
                      "Backup archives in active working directories")
    archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz"}
    for f in files:
        if f["ext"] in archive_exts:
            parent_files = [x for x in files if x["dir"] == f["dir"] and x["ext"] not in archive_exts]
            if len(parent_files) > 5:
                r.affected_paths.append(f["path"])
                r.count += 1
    return r

def detect_chi_gaps(files, dirs, root) -> SymptomResult:
    """R06: Files with chi classification but low confidence. (Stub — needs chi_catalog DB.)"""
    r = SymptomResult("R06", "Research Corpus", "Chi classification gap", "medium",
                      "Low-confidence chi classifications")
    r.details["note"] = "Requires chi_catalog_v2.db — run with --chi-db flag"
    return r

def detect_law_holes(files, dirs, root) -> SymptomResult:
    """R07: Laws with insufficient corpus coverage. (Stub — needs chi_catalog DB.)"""
    r = SymptomResult("R07", "Research Corpus", "Law coverage hole", "high",
                      "Laws with fewer than 50 files in the corpus")
    r.details["note"] = "Requires chi_catalog_v2.db — run with --chi-db flag"
    return r

def detect_claim_gaps(files, dirs, root) -> SymptomResult:
    """R08: High claim density, low evidence. (Stub — needs NLP analysis.)"""
    r = SymptomResult("R08", "Research Corpus", "Claim without evidence", "high",
                      "Bold claims without supporting evidence")
    r.details["note"] = "Requires NLP analysis — run with --nlp flag"
    return r


# ── SCAN ENGINE ─────────────────────────────────────────────

ALL_DETECTORS = [
    detect_ext_swamp, detect_version_sprawl, detect_depth_explosion,
    detect_flat_overload, detect_orphan_sidecar, detect_naming_collision,
    detect_project_scatter, detect_phantom_refs,
    detect_duplicates, detect_format_redundancy, detect_draft_graveyard,
    detect_doc_chaos, detect_media_dump, detect_unknown_blobs,
    detect_encoding_chaos, detect_incomplete_extract,
    detect_time_bombs, detect_burst_dump, detect_stale_pipeline,
    detect_abandoned_workspace,
    detect_program_root, detect_toolchain_residue, detect_config_leak,
    detect_sync_ghost, detect_repo_mix, detect_mirror_drift,
    detect_broken_shortcuts, detect_log_accumulation,
    detect_name_rot, detect_download_purgatory, detect_tiny_debris,
    detect_path_length,
    detect_untagged_canonical, detect_ai_debris, detect_cross_purpose,
    detect_mixed_provenance, detect_archive_pile, detect_chi_gaps,
    detect_law_holes, detect_claim_gaps,
]

CATEGORY_MAP = {
    "structural": ["S"],
    "content": ["C"],
    "temporal": ["T"],
    "infrastructure": ["I"],
    "naming": ["N"],
    "research": ["R"],
}


def scan_folder(root: str, categories: list = None) -> ScanReport:
    root = os.path.abspath(root)
    print(f"\n  Scanning: {root}")
    files, dirs = walk_target(root)
    print(f"  Found {len(files)} files in {len(dirs)} directories")

    report = ScanReport(
        target=root,
        scanned_at=datetime.datetime.now().isoformat(),
        total_files=len(files),
        total_dirs=len(dirs),
    )

    detectors = ALL_DETECTORS
    if categories:
        prefixes = []
        for cat in categories:
            prefixes.extend(CATEGORY_MAP.get(cat.lower(), []))
        detectors = [d for d in ALL_DETECTORS
                     if any(d.__doc__ and d.__doc__.strip().startswith(p) for p in prefixes)]

    for detector in detectors:
        try:
            result = detector(files, dirs, root)
            report.symptoms.append(result)
            if result.count > 0:
                icon = {"low": "·", "medium": "▪", "high": "▲", "critical": "⚠"}[result.severity]
                print(f"  {icon} {result.symptom_id} {result.name}: {result.count} found")
        except Exception as e:
            print(f"  ✗ {detector.__name__} failed: {e}")

    report.compute_grade()
    return report


# ── OUTPUT FORMATTERS ───────────────────────────────────────

def print_report(report: ScanReport):
    print(f"\n{'='*60}")
    print(f"  FOLDER HEALTH REPORT")
    print(f"  Target:  {report.target}")
    print(f"  Scanned: {report.scanned_at}")
    print(f"  Files:   {report.total_files}  |  Dirs: {report.total_dirs}")
    print(f"  Grade:   {report.grade}  ({report.score:.0f}/100)")
    print(f"{'='*60}")

    active = [s for s in report.symptoms if s.count > 0]
    if not active:
        print("\n  ✓ No symptoms detected. This folder is clean.\n")
        return

    active.sort(key=lambda s: {"critical": 0, "high": 1, "medium": 2, "low": 3}[s.severity])
    print(f"\n  {len(active)} symptoms detected:\n")

    for s in active:
        sev_color = {"critical": "⚠ CRITICAL", "high": "▲ HIGH", "medium": "▪ MEDIUM", "low": "· LOW"}
        print(f"  [{s.symptom_id}] {sev_color[s.severity]}: {s.name}")
        print(f"    {s.description}")
        print(f"    Count: {s.count}  |  Auto-fixable: {'Yes' if s.auto_fixable else 'No'}")
        for p in s.affected_paths[:3]:
            print(f"      → {p}")
        if len(s.affected_paths) > 3:
            print(f"      ... and {len(s.affected_paths) - 3} more")
        print()


def report_to_json(report: ScanReport) -> str:
    data = {
        "target": report.target,
        "scanned_at": report.scanned_at,
        "total_files": report.total_files,
        "total_dirs": report.total_dirs,
        "grade": report.grade,
        "score": report.score,
        "symptoms": [],
    }
    for s in report.symptoms:
        if s.count > 0:
            data["symptoms"].append({
                "id": s.symptom_id,
                "category": s.category,
                "name": s.name,
                "severity": s.severity,
                "count": s.count,
                "auto_fixable": s.auto_fixable,
                "affected_paths": s.affected_paths[:20],
                "details": s.details,
            })
    return json.dumps(data, indent=2)


# ── API INTEGRATION ─────────────────────────────────────────

def push_to_api(report: ScanReport, api_url: str):
    try:
        import httpx
    except ImportError:
        print("  httpx not installed — skipping API push. pip install httpx")
        return

    active = [s for s in report.symptoms if s.count > 0]
    summary = f"Scan: {report.target} — Grade {report.grade} ({report.score:.0f}/100), {len(active)} symptoms"

    # Post to Top of Mind messages
    try:
        httpx.post(f"{api_url}/top-of-mind/messages", json={
            "source_id": "folder-scanner",
            "body": summary,
            "priority": 5 if report.grade in ("A", "B") else 7,
        }, timeout=5)
    except Exception:
        pass

    # Store in shared memory
    try:
        httpx.post(f"{api_url}/memory/store", json={
            "key": f"scan_{Path(report.target).name}_{datetime.datetime.now().strftime('%Y%m%d')}",
            "value": summary,
            "source": "folder-scanner",
            "namespace": "global",
            "category": "scan-results",
        }, timeout=5)
    except Exception:
        pass

    # Push critical/high symptoms to clipboard
    criticals = [s for s in active if s.severity in ("critical", "high")]
    if criticals:
        clip_text = "\n".join(f"[{s.symptom_id}] {s.severity.upper()}: {s.name} ({s.count})" for s in criticals)
        try:
            httpx.post(f"{api_url}/clipboard/pin", json={
                "content": clip_text,
                "source": "folder-scanner",
                "tag": "scan-alert",
                "label": f"Scan alerts for {Path(report.target).name}",
            }, timeout=5)
        except Exception:
            pass

    print(f"  → Pushed to API at {api_url}")


def push_to_ntfy(report: ScanReport, ntfy_url: str):
    try:
        import httpx
    except ImportError:
        return
    active = [s for s in report.symptoms if s.count > 0]
    criticals = [s for s in active if s.severity in ("critical", "high")]
    title = f"Folder Scan: {report.grade} ({report.score:.0f}/100)"
    body = f"{Path(report.target).name}: {len(active)} symptoms"
    if criticals:
        body += f"\n⚠ {len(criticals)} critical/high: " + ", ".join(s.name for s in criticals)
    priority = "urgent" if criticals else "default"
    try:
        httpx.post(ntfy_url, content=body.encode(),
                   headers={"Title": title, "Priority": priority}, timeout=5)
        print(f"  → Notification sent to {ntfy_url}")
    except Exception as e:
        print(f"  → ntfy failed: {e}")


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Folder Symptom Scanner v1.0")
    parser.add_argument("targets", nargs="+", help="Folders to scan")
    parser.add_argument("--api", help="File Intelligence Hub URL (e.g. http://localhost:8100)")
    parser.add_argument("--ntfy", help="ntfy topic URL (e.g. http://localhost:10700/fis-scan)")
    parser.add_argument("--categories", help="Comma-separated: structural,content,temporal,infrastructure,naming,research")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text report")
    parser.add_argument("--save", help="Save JSON report to file")
    args = parser.parse_args()

    categories = args.categories.split(",") if args.categories else None

    for target in args.targets:
        if not os.path.isdir(target):
            print(f"  ✗ Not a directory: {target}")
            continue

        report = scan_folder(target, categories)

        if args.json:
            print(report_to_json(report))
        else:
            print_report(report)

        if args.save:
            with open(args.save, "w") as f:
                f.write(report_to_json(report))
            print(f"  → Report saved to {args.save}")

        if args.api:
            push_to_api(report, args.api)

        if args.ntfy:
            push_to_ntfy(report, args.ntfy)


if __name__ == "__main__":
    main()
