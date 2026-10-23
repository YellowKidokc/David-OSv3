"""Canon sidecars — freeze what a file was before anything was declared canonical.

For each group of versions the caller has resolved to one keeper, this writes a
``<keeper>.canon.json`` sidecar naming every sibling, its hash, size and date, and
(optionally) zips the non-canonical versions into one dated archive. Nothing is
deleted: the zip plus the sidecar is the receipt that lets any later run rebuild
the pre-canon state.

Generic over any grouping — duplicate clusters, version families, article
families. It does not decide the keeper; it records the decision.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

SIDECAR_SUFFIX = ".canon.json"


def file_digest(path: Path, limit: int = 1024 * 1024) -> str | None:
    try:
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(limit), b""):
                value.update(chunk)
        return value.hexdigest()
    except OSError:
        return None


def describe(path: str | Path) -> dict[str, object]:
    file = Path(path)
    try:
        stat = file.stat()
        return {"path": str(file), "name": file.name, "bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "sha256": file_digest(file)}
    except OSError:
        return {"path": str(file), "name": file.name, "missing": True}


@dataclass
class CanonGroup:
    keeper: Path
    versions: list[Path]
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {"keeper": describe(self.keeper), "reason": self.reason,
                "versions": [describe(v) for v in self.versions if Path(v) != Path(self.keeper)]}


def sidecar_path(keeper: str | Path) -> Path:
    return Path(str(keeper) + SIDECAR_SUFFIX)


def write_sidecar(group: CanonGroup, *, dry_run: bool = True, extra: Mapping[str, object] | None = None) -> dict[str, object]:
    target = sidecar_path(group.keeper)
    payload = {"canon_sidecar": 1, "sealed": datetime.now().isoformat(timespec="seconds"), **group.to_dict()}
    if extra:
        payload.update(dict(extra))
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"sidecar": str(target), "dry_run": dry_run, "versions": len(payload["versions"])}


def freeze(groups: Iterable[CanonGroup], archive_dir: str | Path, *, dry_run: bool = True,
           label: str = "pre_canon") -> dict[str, object]:
    """Write one sidecar per group and zip every non-canonical version once."""
    groups = list(groups)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = Path(archive_dir) / f"{label}_{stamp}.zip"
    manifest: list[dict[str, object]] = []
    written = 0

    if not dry_run:
        archive.parent.mkdir(parents=True, exist_ok=True)

    zip_handle = None if dry_run else zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED)
    try:
        for group in groups:
            entry = group.to_dict()
            manifest.append(entry)
            written += write_sidecar(group, dry_run=dry_run)["versions"]
            if zip_handle is None:
                continue
            for version in group.versions:
                path = Path(version)
                if path == Path(group.keeper) or not path.exists():
                    continue
                try:
                    zip_handle.write(path, arcname=str(path).replace(":", "").replace("\\", "/"))
                except OSError:
                    continue
        if zip_handle is not None:
            zip_handle.writestr(
                "MANIFEST.json",
                json.dumps({"label": label, "sealed": stamp, "groups": manifest}, indent=2, ensure_ascii=False),
            )
    finally:
        if zip_handle is not None:
            zip_handle.close()

    return {"dry_run": dry_run, "archive": str(archive) if not dry_run else None,
            "groups": len(groups), "versions_recorded": written,
            "manifest_entries": len(manifest)}


def groups_from_clusters(clusters: Sequence[Mapping[str, object]], keeper_key: str = "keep",
                         members_key: str = "files", reason_key: str = "reason") -> list[CanonGroup]:
    """Adapt duplicate/near-duplicate scanner output into CanonGroups."""
    out: list[CanonGroup] = []
    for cluster in clusters:
        members = [Path(str(m)) for m in (cluster.get(members_key) or [])]
        keeper = cluster.get(keeper_key) or (members[0] if members else None)
        if not keeper or not members:
            continue
        out.append(CanonGroup(Path(str(keeper)), members, str(cluster.get(reason_key, ""))))
    return out
