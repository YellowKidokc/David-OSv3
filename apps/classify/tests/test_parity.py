"""Compatibility tests: engines match legacy sources; output follows classification.v1; no network by default."""
import importlib.util, json, sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
sys.path.insert(0, str(APP / "src"))
import run  # noqa: E402

LEGACY_FIS_DIR = ROOT / "file-intelligence-system"
LEGACY_CHI = Path(r"D:\GitHub\FIS\chi_classifier.py")

TEXTS = {
    "grace.md": "# Grace and Coherence\n\nGrace restores order. Entropy increases unless information is supplied. "
                "The Master Equation links coherence, truth and moral law. Evidence: measured data, p < 0.05. " * 8,
    "code.py": "import os\n\ndef main():\n    return os.getcwd()\n",
    "notes.txt": "Meeting notes about the budget, schedule and the quarterly plan. " * 10,
    "page.html": "<html><body><h1>Quantum Decoherence</h1><p>Observation collapses superposition; measurement and entanglement.</p></body></html>",
    "empty.md": "",
}

@pytest.fixture()
def corpus(tmp_path):
    for n, t in TEXTS.items():
        (tmp_path / n).write_text(t, encoding="utf-8")
    return sorted(tmp_path.iterdir())

def _load(name, path, extra_path=None):
    if not path.exists():
        pytest.skip(f"legacy {path} not present")
    if extra_path:
        sys.path.insert(0, str(extra_path))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    if extra_path:
        sys.path.remove(str(extra_path))
    return m

def _strip(d):  # drop fields that legitimately depend on wall-clock time
    d = dict(d); d.pop("lossless_address", None); d.pop("lossless_address_detail", None); return d

def test_fis_engine_parity(corpus):
    legacy = _load("legacy_fis_classifier", LEGACY_FIS_DIR / "fis_classifier.py", LEGACY_FIS_DIR)
    for p in corpus:
        assert _strip(legacy.classify_file(str(p))) == _strip(run.fis_classifier.classify_file(str(p))), p.name

def test_chi_engine_parity(corpus):
    legacy = _load("legacy_chi_classifier", LEGACY_CHI)
    for p in corpus:
        t = p.read_text(encoding="utf-8")
        assert legacy.classify_chi_factor([], t, p.name) == run.chi_classifier.classify_chi_factor([], t, p.name)

@pytest.mark.parametrize("engine", ["fis", "chi"])
def test_contract(corpus, engine, monkeypatch):
    monkeypatch.setattr(run.fis_classifier, "ai_classify", lambda *a, **k: pytest.fail("network call without --allow-ai"))
    schema = json.loads((ROOT / "shared/contracts/classification.v1.schema.json").read_text())
    recs = run.classify_paths(corpus, engine)
    assert len(recs) == len(corpus)
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    for r in recs:
        assert r["status"] != "error", r.get("error")
        for k in schema["required"]:
            assert k in r, k
        assert r["schema_version"] == "classification.v1" and len(r["sha256"]) == 64
        for l in r["labels"]:
            assert 0 <= l["confidence"] <= 1
        if jsonschema:
            jsonschema.validate(r, schema)
