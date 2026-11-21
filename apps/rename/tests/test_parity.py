"""Compatibility tests: same proposals as legacy 03_RENAMING engine; valid rename-proposal.v1; touches nothing."""
import hashlib, importlib.util, json, os, sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
LEGACY = ROOT / "03_CLASSIFY" / "03_RENAMING" / "rename_engine.py"
sys.path.insert(0, str(APP / "src"))
import run  # noqa: E402

FILES = {
    "grace and coherence draft.md": "# Grace and Coherence\n\nTheology of grace, entropy and the Master Equation.\n",
    "notes/physics_decoherence_v2.txt": "Quantum decoherence and measurement notes.",
    "PHY__PAP__already_named__20260101__DR.md": "already in the scheme",
    "copy1.md": "same bytes", "copy2.md": "same bytes",
}

@pytest.fixture()
def folder(tmp_path):
    for n, t in FILES.items():
        p = tmp_path / n; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t, encoding="utf-8")
        os.utime(p, (1_700_000_000, 1_700_000_000))
    return tmp_path

def _snapshot(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime)
            for p in sorted(root.rglob("*")) if p.is_file()}

def _key(props):
    return [(str(p.path), p.proposed, p.confidence, p.why, p.domain, p.type, p.status, p.sha256, p.flag) for p in props]

def test_parity_with_legacy(folder):
    if not LEGACY.exists():
        pytest.skip("legacy engine missing")
    sys.path.insert(0, str(LEGACY.parent))
    spec = importlib.util.spec_from_file_location("legacy_rename_engine", LEGACY)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules["legacy_rename_engine"] = legacy  # dataclasses need the module registered
    try:
        spec.loader.exec_module(legacy)
    except ImportError as e:
        pytest.skip(f"legacy engine needs David-OS deps: {e}")
    finally:
        sys.path.remove(str(LEGACY.parent))
    assert _key(legacy.propose(folder)) == _key(run.rename_engine.propose(folder))

def test_contract_and_read_only(folder, tmp_path_factory):
    before = _snapshot(folder)
    out = tmp_path_factory.mktemp("out") / "r.jsonl"
    assert run.main([str(folder), "--out", str(out)]) == 0
    assert _snapshot(folder) == before, "rename app modified the scanned folder"
    schema = json.loads((ROOT / "shared/contracts/rename-proposal.v1.schema.json").read_text())
    recs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(recs) == len(FILES)
    for r in recs:
        for k in schema["required"]:
            assert k in r, k
        assert r["review_state"] == "proposed" and len(r["sha256"]) == 64
        assert r["recovery"]["sha256"] == r["sha256"]
    by = {Path(r["source_path"]).name: r for r in recs}
    assert by["PHY__PAP__already_named__20260101__DR.md"]["flag"] == "already named"
    assert by["copy1.md"]["status"] == "needs_review"  # duplicates are never auto-ok
