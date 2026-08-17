"""Hash worker for deterministic file identity."""
from __future__ import annotations

import hashlib
from pathlib import Path


def hash_file(path: str, *, algorithm: str = "sha256") -> dict[str, object]:
    file_path = Path(path)
    h = hashlib.new(algorithm)
    size = 0
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            h.update(chunk)
    return {"path": str(file_path), "algorithm": algorithm, "digest": h.hexdigest(), "size_bytes": size}
