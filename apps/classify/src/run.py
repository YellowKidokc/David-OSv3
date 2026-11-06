"""classify app entry point (read-only).

Engines (plug-ins, all unchanged copies of legacy code):
  fis  - file-intelligence-system/fis_classifier.py: domain, CHI factor, law,
         content type, evidence, document type. Default.
  chi  - FIS chi_classifier.py: Master Equation CHI factor from text + filename.
  lexicon - Rust Pass 1 lexicon classifier (rust/lexicon_classify + lexicon/LEXICON_LOOKUP.json):
         10-axis output per classification_2_0.json. Runs as a separate process.

Writes one classification.v1 record per file to data/classify/classification.v1.jsonl.
Never moves, renames or deletes. The fis engine's Claude API fallback is OFF
unless --allow-ai is passed (it would send file text to api.anthropic.com).
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC / "engines" / "fis"))
sys.path.insert(0, str(SRC / "engines" / "chi"))
import fis_classifier  # noqa: E402
import chi_classifier  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

APP = SRC.parent
LEXICON = APP / "lexicon" / "LEXICON_LOOKUP.json"
TAXONOMY = APP / "lexicon" / "classification_2_0.json"


def lexicon_exe() -> Path | None:
    for n in ("lexicon_classify.exe", "lexicon_classify"):
        p = APP / "rust" / "lexicon_classify" / "target" / "release" / n
        if p.is_file():
            return p
    return None


def run_lexicon(paths: list[Path], ignore_frontmatter: bool = False) -> list[dict]:
    """Classify files with the Rust lexicon engine; returns classification.v1 records."""
    exe = lexicon_exe()
    if exe is None:
        raise RuntimeError("lexicon engine not built: cd rust/lexicon_classify && cargo build --release")
    recs: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.jsonl"
        for i in range(0, len(paths), 200):  # chunked: Windows command-line length limit
            cmd = [str(exe), "--lexicon", str(LEXICON), "--taxonomy", str(TAXONOMY), "--out", str(out)]
            if ignore_frontmatter:
                cmd.append("--ignore-frontmatter")
            subprocess.run(cmd + [str(x) for x in paths[i:i + 200]], check=True, capture_output=True)
            recs += [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in recs:
        r.pop("cache_key", None)
    return recs

APP_VERSION = "0.1.0"
ROOT = SRC.parents[2]
DEFAULT_OUT = ROOT / "data" / "classify" / "classification.v1.jsonl"
TEXT_EXTS = {".md", ".txt", ".html", ".htm", ".rst", ".tex", ".py", ".json", ".csv", ".yaml", ".yml"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_fis(path: Path, allow_ai: bool) -> tuple[list, list, dict]:
    if allow_ai:
        r = fis_classifier.classify(str(path))
    else:
        r = fis_classifier.classify_file(str(path))  # local only, no network
    conf = float(r.get("confidence", 0))
    labels = [{"label": f"chi:{r['chi_factor']}", "confidence": conf},
              {"label": f"domain:{r['domain']['name']}", "confidence": conf},
              {"label": f"law:{r['law']['name']}", "confidence": conf},
              {"label": f"content_type:{r['content_type']}", "confidence": conf},
              {"label": f"doc_type:{r['doc_type']}", "confidence": float(r.get("type_confidence", 0))}]
    evidence = [str(e) for e in (r.get("type_evidence") or [])][:10]
    return labels, evidence, r


def run_chi(path: Path) -> tuple[list, list, dict]:
    text = path.read_text(encoding="utf-8", errors="replace")[:6000] if path.suffix.lower() in TEXT_EXTS else ""
    r = chi_classifier.classify_chi_factor([], text, path.name)
    # chi_classifier reports confidence as a percentage (0-100); contract wants 0-1.
    labels = [{"label": f"chi:{r['primary_factor']}", "confidence": min(1.0, float(r.get("confidence", 0)) / 100)}]
    return labels, [str(m) for m in r.get("matched", [])][:10], r


def classify_paths(paths: list[Path], engine: str = "fis", allow_ai: bool = False) -> list[dict]:
    if engine == "lexicon":
        return run_lexicon(paths)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for p in paths:
        rec = {"schema_version": "classification.v1", "producer": f"classify@{APP_VERSION}",
               "created_at": now, "source_path": str(p), "classifier": engine}
        try:
            rec["sha256"] = sha256_file(p)
            labels, evidence, raw = run_fis(p, allow_ai) if engine == "fis" else run_chi(p)
            low = min((l["confidence"] for l in labels), default=0) < 0.45
            rec.update(status="needs_review" if low else "ok", labels=labels, evidence=evidence, raw=raw)
        except Exception as e:  # never stop a batch for one file
            rec.setdefault("sha256", "0" * 64)
            rec.update(status="error", labels=[], error=f"{type(e).__name__}: {e}")
        out.append(rec)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="David-OS classify app (read-only)")
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--engine", choices=["fis", "chi", "lexicon"], default="fis")
    ap.add_argument("--allow-ai", action="store_true", help="let fis engine call Claude API for low-confidence files")
    ap.add_argument("--max-files", type=int, default=500)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    files = []
    for folder in a.folders:
        p = Path(folder)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(x for x in p.rglob("*") if x.is_file())
        else:
            print(f"WARNING: {folder} not found, skipping")
    files = sorted(files)[: a.max_files]
    print(f"Classifying {len(files)} files with engine={a.engine} ai={'on' if a.allow_ai else 'off'}")
    recs = classify_paths(files, a.engine, a.allow_ai)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    counts = {}
    for r in recs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{counts} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
