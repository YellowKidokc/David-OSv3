"""Compatibility tests: app must match legacy FIS fingerprint.py and emit valid fingerprint.v1."""
import importlib.util, json, sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
LEGACY = Path(r"D:\GitHub\FIS\fingerprint.py")
sys.path.insert(0, str(APP / "src"))
import fingerprint as app_fp  # noqa: E402
import run  # noqa: E402

BODY = " ".join(f"sentence {i} speaks of grace truth order and coherence in measure {i * 7}." for i in range(80))
TEXTS = {
    "a.md": BODY,
    "b.txt": BODY + " One extra closing remark appended here.",
    "c.html": "<html><body><article>" + "Entropy rises unless information is restored by a source. " * 25 + "</article></body></html>",
    "d.md": "short",
    "e.txt": "Unicode ψ ∞ χ — coherence ledger entry number seven repeated. " * 20,
}

@pytest.fixture()
def corpus(tmp_path):
    for n, t in TEXTS.items():
        (tmp_path / n).write_text(t, encoding="utf-8")
    return sorted(tmp_path.iterdir())

def _legacy():
    if not LEGACY.exists():
        pytest.skip("legacy FIS fingerprint.py not present")
    spec = importlib.util.spec_from_file_location("legacy_fingerprint", LEGACY)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def test_parity_with_legacy(corpus):
    legacy = _legacy()
    for p in corpus:
        old, new = legacy.process_file(p), app_fp.process_file(p)
        assert old == new, p.name

def test_rust_and_python_agree(corpus):
    if app_fp._rust_minhash_exe() is None:
        pytest.skip("rust not built")
    sets = [app_fp.shingle(app_fp.normalize(p.read_text(encoding="utf-8"))) for p in corpus]
    assert app_fp.minhash_signatures_batch(sets) == [app_fp._minhash_signature_py(s) for s in sets]

def test_records_match_contract(corpus):
    schema = json.loads((ROOT / "shared/contracts/fingerprint.v1.schema.json").read_text())
    recs = run.build_records(corpus)
    assert len(recs) == len(corpus)
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    for r in recs:
        for k in schema["required"]:
            assert k in r, k
        assert r["schema_version"] == "fingerprint.v1"
        if jsonschema:
            jsonschema.validate(r, schema)
    by = {Path(r["source_path"]).name: r for r in recs}
    assert by["d.md"]["status"] == "skipped"
    assert any(n["path"].endswith("b.txt") for n in by["a.md"]["near_duplicates"])
