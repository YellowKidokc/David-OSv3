"""fingerprint app entry point.

Scans folders (read-only), fingerprints documents with the unchanged legacy
engine (fingerprint.py, Rust-accelerated when built), and writes one
fingerprint.v1 record per file to data/fingerprint/fingerprint.v1.jsonl.
Never moves, renames, or deletes anything.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fingerprint as fp  # noqa: E402

APP_VERSION = "0.1.0"
PRODUCER = f"fingerprint@{APP_VERSION}"
ROOT = Path(__file__).resolve().parents[3]          # David-OSv3
DEFAULT_OUT = ROOT / "data" / "fingerprint" / "fingerprint.v1.jsonl"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_records(paths: list[Path], threshold: float = 0.7) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    recs, docs = [], []
    for p in paths:
        base = {"schema_version": "fingerprint.v1", "producer": PRODUCER, "created_at": now,
                "source_path": str(p)}
        try:
            base["sha256"] = sha256_file(p)
        except OSError as e:
            recs.append({**base, "sha256": "0" * 64, "status": "error", "error": str(e)})
            continue
        d = fp.process_file(p)
        if d is None:
            recs.append({**base, "status": "skipped", "content_hash": ""})
        elif "error" in d:
            recs.append({**base, "status": "error", "content_hash": "", "error": d["error"]})
        else:
            rec = {**base, "status": "ok", "content_hash": d["content_hash"], "minhash_k": 5,
                   "minhash": [str(v) for v in d["signature"]], "near_duplicates": []}
            recs.append(rec); docs.append((rec, d["signature"]))
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            sim = fp.jaccard_minhash(docs[i][1], docs[j][1])
            if sim >= threshold:
                a, b = docs[i][0], docs[j][0]
                a["near_duplicates"].append({"sha256": b["sha256"], "path": b["source_path"], "similarity": round(sim, 4)})
                b["near_duplicates"].append({"sha256": a["sha256"], "path": a["source_path"], "similarity": round(sim, 4)})
    return recs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="David-OS fingerprint app (read-only)")
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--threshold", type=float, default=0.7)
    ap.add_argument("--max-files", type=int, default=500)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    files = []
    for folder in a.folders:
        p = Path(folder)
        if not p.exists():
            print(f"WARNING: {folder} not found, skipping"); continue
        for ext in fp.SUPPORTED:
            files.extend(p.rglob(f"*{ext}"))
    files = sorted(files)[: a.max_files]
    print(f"Fingerprinting {len(files)} files (rust={'yes' if fp._rust_minhash_exe() else 'no'})")
    recs = build_records(files, a.threshold)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = sum(r["status"] == "ok" for r in recs)
    nd = sum(bool(r.get("near_duplicates")) for r in recs)
    print(f"ok={ok} with_near_duplicates={nd} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
