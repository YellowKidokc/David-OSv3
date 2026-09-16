#!/usr/bin/env python3
"""Read corpus.llmanifest.json: list, inspect, search, verify, reconstruct."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def corpus_root(manifest_path: Path) -> Path:
    return manifest_path.resolve().parent


def read_packet(manifest_path: Path, record: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    packet_path = corpus_root(manifest_path) / record["packet_file"]
    with zipfile.ZipFile(packet_path, "r") as z:
        metadata = json.loads(z.read("packet.json").decode("utf-8"))
        original_path = "original/" + metadata["source"]["relative_path"]
        raw = z.read(original_path)
    return metadata, raw


def command_list(_manifest_path: Path, manifest: dict[str, Any]) -> None:
    for index, record in enumerate(manifest["files"], start=1):
        marker = "TEXT" if record["is_text"] else "BIN"
        ratio = record.get("compression_ratio") or "-"
        profile = record.get("payload_profile") or ""
        print(f"{index:04d} [{marker}] {ratio:>6} {profile:18} {record['relative_path']}")


def command_inspect(manifest_path: Path, manifest: dict[str, Any], target: str) -> None:
    matches = [
        record
        for record in manifest["files"]
        if target.lower() in record["relative_path"].lower() or target == record["packet_id"]
    ]
    if not matches:
        print("No matching file.")
        return
    for record in matches:
        metadata, _ = read_packet(manifest_path, record)
        print(json.dumps(metadata.get("compact") or metadata, ensure_ascii=False, indent=2))


def command_verify(manifest_path: Path, manifest: dict[str, Any]) -> None:
    failures = 0
    print("Verifying corpus...\n")
    for record in manifest["files"]:
        try:
            _, raw = read_packet(manifest_path, record)
            actual = sha256_bytes(raw)
            expected = record["source_sha256"]
            if actual != expected:
                failures += 1
                print(f"[FAIL] {record['relative_path']}")
            else:
                print(f"[ OK ] {record['relative_path']}")
        except Exception as exc:
            failures += 1
            print(f"[ERR ] {record['relative_path']}: {exc}")
    print()
    if failures:
        print(f"Verification FAILED: {failures} problem(s)")
        raise SystemExit(1)
    print("Verification PASSED.")
    print("All original files match their SHA-256 hashes.")


def command_reconstruct(manifest_path: Path, manifest: dict[str, Any], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for record in manifest["files"]:
        metadata, raw = read_packet(manifest_path, record)
        output_path = destination / Path(metadata["source"]["relative_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(raw)
        print(f"[WRITE] {output_path}")
    print(f"\nReconstructed {len(manifest['files'])} files.")


def command_search(manifest_path: Path, manifest: dict[str, Any], query: str) -> None:
    q = query.lower()
    results = []
    for record in manifest["files"]:
        metadata, raw = read_packet(manifest_path, record)
        if not metadata["source"]["is_text"]:
            continue
        text = raw.decode("utf-8", errors="replace")
        count = text.lower().count(q)
        if count:
            results.append({"path": metadata["source"]["relative_path"], "occurrences": count})
    results.sort(key=lambda item: (-item["occurrences"], item["path"]))
    for result in results:
        print(f"{result['occurrences']:5d}  {result['path']}")
    print(f"\n{len(results)} matching files.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read an LLP lossless corpus.")
    parser.add_argument("manifest", help="corpus.llmanifest.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("target")
    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    sub.add_parser("verify")
    reconstruct_parser = sub.add_parser("reconstruct")
    reconstruct_parser.add_argument("destination")
    args = parser.parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    if args.command == "list":
        command_list(manifest_path, manifest)
    elif args.command == "inspect":
        command_inspect(manifest_path, manifest, args.target)
    elif args.command == "search":
        command_search(manifest_path, manifest, args.query)
    elif args.command == "verify":
        command_verify(manifest_path, manifest)
    elif args.command == "reconstruct":
        command_reconstruct(manifest_path, manifest, Path(args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
