"""Central path policy for generated FIS artifacts."""
from __future__ import annotations

from pathlib import Path


GENERATED_FISNOTES_ENABLED = False
BLOCKED_FISNOTE_DRIVES = {"Z:"}
BLOCKED_FISNOTE_ROOTS = (Path(r"D:\GitHub"), Path(r"G:\GitHub"))


PROTECTED_ROOTS: list[Path] = []


def protect_root(path: str | Path) -> Path:
    """Mark *path* read-only for every write that routes through this policy.

    Generic: any caller (scanner, file action worker, sidecar writer) can declare a
    folder off-limits for the life of the process, so a scan never writes into the
    folder it is examining.
    """
    resolved = Path(path).expanduser().resolve()
    if resolved not in PROTECTED_ROOTS:
        PROTECTED_ROOTS.append(resolved)
    return resolved


def clear_protected_roots() -> None:
    PROTECTED_ROOTS.clear()


def _under(candidate: Path, root: Path) -> bool:
    text, root_text = str(candidate).rstrip("\\/").lower(), str(root).rstrip("\\/").lower()
    return text == root_text or text.startswith(root_text + "\\") or text.startswith(root_text + "/")


def write_allowed(path: str | Path) -> bool:
    """Whether any file may be created or modified at *path*."""
    candidate = Path(path).expanduser().resolve()
    return not any(_under(candidate, root) for root in PROTECTED_ROOTS)


def require_write_allowed(path: str | Path) -> None:
    if not write_allowed(path):
        raise PermissionError(f"{path} is inside a protected root; this run is read-only there.")


def drive_key(path: str | Path) -> str:
    """Return an uppercase Windows drive key without requiring the path to exist."""
    return Path(path).drive.upper()


def fisnote_write_allowed(path: str | Path) -> bool:
    """Whether generated `.fisnote` artifacts may be written below *path*.

    This affects only note sidecars. HTML and database output have separate
    policies and remain allowed on Z:.
    """
    if not GENERATED_FISNOTES_ENABLED:
        return False
    candidate = Path(path)
    if drive_key(candidate) in BLOCKED_FISNOTE_DRIVES:
        return False
    candidate_text = str(candidate).rstrip("\\/").lower()
    return not any(
        candidate_text == str(root).lower()
        or candidate_text.startswith(str(root).rstrip("\\/").lower() + "\\")
        for root in BLOCKED_FISNOTE_ROOTS
    )


def require_fisnote_write_allowed(path: str | Path) -> None:
    if not fisnote_write_allowed(path):
        raise PermissionError(
            f"Generated .fisnote writes are disabled globally at {path}; use HTML or database output instead."
        )
