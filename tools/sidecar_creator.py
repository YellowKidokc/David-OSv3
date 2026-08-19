#!/usr/bin/env python3
"""Create approved David-OS sidecars beside one selected file.

Designed for Windows Explorer's right-click menu. The source file is only
read for identity and SHA-256; this tool never renames, moves, or edits it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from tkinter import END, StringVar, Text, Tk, messagebox
from tkinter import ttk

TAXONOMY_ROOT = Path(os.environ.get(
    "THEOPHYSICS_TAXONOMY_ROOT",
    str(Path(__file__).resolve().parents[1] / "file-intelligence-system"),
))
if str(TAXONOMY_ROOT) not in sys.path:
    sys.path.insert(0, str(TAXONOMY_ROOT))
try:
    from theophysics_taxonomy import parse_filename
except ImportError:
    parse_filename = None


SIDECARS = {
    "Canon status (.canon.sidecar.json)": ".canon.sidecar.json",
    "Identity (.fmeta)": ".fmeta",
    "Classification (.chi)": ".chi",
    "Research note (.fisnote)": ".fisnote",
}
STATUSES = ("candidate", "canonical", "reference", "working", "archived", "unknown")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_path(source: Path, kind: str) -> Path:
    return Path(str(source) + SIDECARS[kind])


def source_identity(source: Path) -> dict[str, object]:
    stat = source.stat()
    identity = {
        "source_path": str(source.resolve()),
        "source_name": source.name,
        "source_extension": source.suffix.lower(),
        "source_bytes": stat.st_size,
        "source_modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "source_sha256": sha256(source),
    }
    parsed = parse_filename(source.name) if parse_filename else None
    identity["filename_grammar"] = "theophysics-domain-type-v1" if parsed else "unclassified"
    identity["domain_code"] = parsed["domain_code"] if parsed else None
    identity["type_code"] = parsed["type_code"] if parsed else None
    identity["filename_parse"] = parsed
    return identity


def render(source: Path, kind: str, status: str, classification: str, notes: str) -> str:
    identity = source_identity(source)
    created = utc_now()
    suffix = SIDECARS[kind]
    if suffix == ".canon.sidecar.json":
        payload = {
            "sidecar_type": "canon_status",
            "version": "1.0",
            "created_at": created,
            "created_by": "David-OS Sidecar Creator",
            "status": status,
            "classification": classification or "unclassified",
            "notes": notes,
            "lineage": {"source": identity, "parent_sidecars": [], "rulings": []},
            "filename_grammar": identity["filename_grammar"],
            "domain_code": identity["domain_code"],
            "type_code": identity["type_code"],
            "claim_ids": [],
            "evidence_tier": "unknown",
            "contradictions": [],
            "wanted": [],
            "written": [],
            "boundary": "Sidecar metadata only. It does not alter, admit, move, or canonize the source file.",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    lines = [
        "# David-OS sidecar",
        f"sidecar_type: {suffix.lstrip('.')}",
        f"created_at: {created}",
        f"created_by: David-OS Sidecar Creator",
        f"status: {status}",
        f"classification: {classification or 'unclassified'}",
        f"source_path: {identity['source_path']}",
        f"source_name: {identity['source_name']}",
        f"source_extension: {identity['source_extension']}",
        f"source_bytes: {identity['source_bytes']}",
        f"source_modified_utc: {identity['source_modified_utc']}",
        f"source_sha256: {identity['source_sha256']}",
        f"filename_grammar: {identity['filename_grammar']}",
        f"domain_code: {identity['domain_code'] or 'UNRESOLVED'}",
        f"type_code: {identity['type_code'] or 'UNRESOLVED'}",
        "boundary: Sidecar metadata only. It does not alter, admit, move, or canonize the source file.",
        "notes:",
        notes,
        "",
    ]
    return "\n".join(lines)


def write_sidecar(source: Path, kind: str, status: str, classification: str, notes: str, overwrite: bool = False) -> Path:
    if not source.is_file():
        raise ValueError(f"Not a file: {source}")
    target = output_path(source, kind)
    if target.exists() and not overwrite:
        raise FileExistsError(str(target))
    target.write_text(render(source, kind, status, classification, notes), encoding="utf-8")
    return target


def gui(source: Path) -> None:
    root = Tk()
    root.title("Create Theophysics Sidecar")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=14)
    frame.grid()
    ttk.Label(frame, text="Selected file:").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text=str(source), wraplength=620).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
    kind = StringVar(value="Canon status (.canon.sidecar.json)")
    status = StringVar(value="candidate")
    classification = StringVar(value="")
    ttk.Label(frame, text="Sidecar piece").grid(row=2, column=0, sticky="w")
    ttk.Combobox(frame, textvariable=kind, values=list(SIDECARS), state="readonly", width=42).grid(row=2, column=1, sticky="ew")
    ttk.Label(frame, text="Status").grid(row=3, column=0, sticky="w", pady=(8, 0))
    ttk.Combobox(frame, textvariable=status, values=STATUSES, state="readonly", width=42).grid(row=3, column=1, sticky="ew", pady=(8, 0))
    ttk.Label(frame, text="Classification").grid(row=4, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(frame, textvariable=classification, width=45).grid(row=4, column=1, sticky="ew", pady=(8, 0))
    ttk.Label(frame, text="Notes").grid(row=5, column=0, sticky="nw", pady=(8, 0))
    notes = Text(frame, width=46, height=7)
    notes.grid(row=5, column=1, sticky="ew", pady=(8, 0))

    def create() -> None:
        target = output_path(source, kind.get())
        overwrite = False
        if target.exists():
            overwrite = messagebox.askyesno("Replace sidecar?", f"A sidecar already exists:\n{target.name}\n\nReplace it?")
            if not overwrite:
                return
        try:
            result = write_sidecar(source, kind.get(), status.get(), classification.get().strip(), notes.get("1.0", END).strip(), overwrite)
        except Exception as exc:
            messagebox.showerror("Sidecar not created", str(exc))
            return
        messagebox.showinfo("Sidecar created", f"Created:\n{result.name}\n\nThe source file was not changed.")
        root.destroy()

    ttk.Button(frame, text="Create Sidecar", command=create).grid(row=6, column=1, sticky="e", pady=(12, 0))
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create David-OS sidecars beside a file")
    parser.add_argument("source")
    parser.add_argument("--kind", choices=list(SIDECARS))
    parser.add_argument("--status", choices=STATUSES, default="candidate")
    parser.add_argument("--classification", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    if args.kind:
        print(write_sidecar(source, args.kind, args.status, args.classification, args.notes, args.overwrite))
    else:
        gui(source)


if __name__ == "__main__":
    main()
