"""Shared, dependency-free scanning helpers."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from pathlib import Path

from .models import Severity, SymptomResult


def root(path: str | os.PathLike[str]) -> Path:
    value = Path(path).expanduser().resolve()
    if not value.is_dir():
        raise NotADirectoryError(value)
    return value


def walk(path: str | os.PathLike[str]) -> tuple[list[Path], list[Path]]:
    base = root(path); files: list[Path] = []; dirs: list[Path] = [base]
    for current, names, filenames in os.walk(base, followlinks=False):
        here = Path(current)
        names[:] = [name for name in names if not (here / name).is_symlink()]
        dirs.extend(here / name for name in names)
        files.extend(here / name for name in filenames if not (here / name).is_symlink())
    return files, dirs


def result(code: str, name: str, category: str, severity: Severity, path: Path,
           message: str, auto: bool = False, **evidence: object) -> SymptomResult:
    return SymptomResult(code, name, category, severity, path, message, auto, evidence)


def matches(files: Iterable[Path], pattern: str) -> list[Path]:
    regex = re.compile(pattern, re.I)
    return [file for file in files if regex.search(file.name)]


def digest(path: Path) -> str | None:
    try:
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""): value.update(chunk)
        return value.hexdigest()
    except OSError:
        return None


TEXT_EXTS = {".txt", ".md", ".rst", ".csv", ".json", ".xml", ".html", ".htm", ".py", ".js", ".yaml", ".yml"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt"}
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp3", ".wav", ".mp4", ".mov", ".avi"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"}
