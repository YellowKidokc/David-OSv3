"""Preserve legacy source candidates without importing or starting legacy apps.

Run from any directory. Existing snapshots are verified, never overwritten.
Databases, logs, caches, archives and user documents stay at their source paths.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "tools" / "file-intelligence-sources"
ROOTS = {
    "FIS": Path(r"D:\DONT TOUCH BOOT UP\FIS"),
    "filetagger": Path(r"D:\DONT TOUCH BOOT UP\filetagger"),
}
EXTENSIONS = {".py", ".ps1", ".bat", ".cmd", ".sh", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"}
SKIP = {".git", ".venv", "venv", "__pycache__", "node_modules", "target", "DISABLE_RECEIPTS"}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files(root: Path):
    for child in sorted(root.iterdir()):
        if child.is_symlink() or child.name in SKIP:
            continue
        if child.is_dir():
            yield from files(child)
        elif child.is_file():
            yield child


def inspect_python(path: Path) -> dict:
    if path.suffix.lower() != ".py":
        return {}
    try:
        tree = ast.parse(path.read_bytes(), filename=str(path))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        return {"syntax": "passed", "imports": sorted(imports),
                "description": (ast.get_docstring(tree) or "").split("\n")[0]}
    except (SyntaxError, UnicodeError, ValueError) as exc:
        return {"syntax": "failed", "error": str(exc)}


def main() -> None:
    # Hash only maintained application locations; avoid historical sidecar trees.
    existing = {}
    for name in ("fis", "engine", "agents", "scripts", "gui", "file-intelligence-system"):
        for path in files(REPO / name):
            if path.suffix.lower() in EXTENSIONS:
                existing.setdefault(digest(path), []).append(str(path.relative_to(REPO)))
    records, excluded = [], []
    for label, root in ROOTS.items():
        if not root.is_dir():
            raise FileNotFoundError(root)
        for source in files(root):
            relative = source.relative_to(root)
            # Runtime state is not portable code or configuration.
            if (source.suffix.lower() not in EXTENSIONS or
                    source.name.endswith("_status.json") or
                    source.name in {"consciousness_scan.json", "consciousness_math.json"}):
                excluded.append({"source": str(source), "bytes": source.stat().st_size,
                                 "reason": "runtime data, generated output, or non-source asset; retained in place"})
                continue
            target = DEST / "snapshots" / label / relative
            before = digest(source)
            if target.exists():
                if digest(target) != before:
                    raise RuntimeError(f"Snapshot differs; refusing overwrite: {target}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            if digest(target) != before or digest(source) != before:
                raise RuntimeError(f"Source changed or copy verification failed: {source}")
            records.append({"source": str(source), "snapshot": str(target.relative_to(REPO)),
                            "sha256": before, "bytes": target.stat().st_size,
                            "existing_identical": existing.get(before, []),
                            "status": "reference candidate; not enabled", **inspect_python(target)})
    result = {"scope": "two explicitly named boot folders; eligible source and configuration files",
              "source_mutations": False, "legacy_code_executed": False,
              "files": records, "retained_in_place": excluded}
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"copied_and_verified": len(records), "retained_in_place": len(excluded),
                      "identical_to_existing": sum(bool(r["existing_identical"]) for r in records),
                      "python_syntax_failures": sum(r.get("syntax") == "failed" for r in records),
                      "manifest": str(DEST / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
