# fis-op: gov
"""Operation map — the index of every op-coded module.

Every operation module carries a `# fis-op: <code>` tag at the top. This scans
them into one manifest: {op_code -> [modules]}. That is the catalog a future
"try everything" script consumes — enumerate the operations of a given family
(or all of them) and brute-force run them when that's the only way to crack a
problem. We can't rename live .py files (imports break), so the code lives in
the tag, not the filename — same label, no breakage.

    op codes: lok idn und sim dec act gov lrn aut  (+ pipeline)
"""
from __future__ import annotations

import re
from pathlib import Path

FIS_DIR = Path(__file__).parent
TAG = re.compile(r"#\s*fis-op:\s*([a-z]+)")


def scan(root: Path = FIS_DIR) -> dict[str, list[str]]:
    """{op_code: [relative module paths]} read from the # fis-op: tags."""
    out: dict[str, list[str]] = {}
    for py in sorted(root.rglob("*.py")):
        if py.name in ("__init__.py", "opmap.py"):
            continue
        head = "\n".join(py.read_text(encoding="utf-8", errors="replace").splitlines()[:3])
        m = TAG.search(head)
        if m:
            out.setdefault(m.group(1), []).append(str(py.relative_to(root)))
    return out


def manifest() -> dict:
    """Full catalog: modules per code + the named handlers on the shelf."""
    codes = scan()
    try:
        from .handlers import registry as _reg
        handlers = _reg.available()
    except Exception:
        handlers = []
    return {"codes": codes,
            "handlers": handlers,
            "counts": {c: len(v) for c, v in sorted(codes.items())},
            "total_modules": sum(len(v) for v in codes.values())}


def by_code(code: str) -> list[str]:
    return scan().get(code, [])
