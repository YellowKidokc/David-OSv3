"""Rust lexicon engine: contract, taxonomy vocabulary, read-only, determinism, frontmatter, R3."""
import hashlib, json, os, sys
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
sys.path.insert(0, str(APP / "src"))
import run  # noqa: E402

pytestmark = pytest.mark.skipif(run.lexicon_exe() is None, reason="rust/lexicon_classify not built")

FILES = {
    "gravity_paper.md": "# Gravity and Grace\n\nGravity curves spacetime. Sin is a curvature; grace restores the geodesic. "
                        "This proves the bridge. Evidence: measured data. Breaks if the prediction fails.\n",
    "stamped.md": "---\ntitle: \"x\"\ntype: \"series_paper\"\nchi_primary: \"E\"\nstatus: \"final\"\ncanon_status: \"admitted\"\n"
                  "canon_role: \"bridge\"\ndomain: \"theophysics\"\n---\n\nGravity gravity gravity curvature.\n",
    "tool.py": "import os\nprint(os.getcwd())\n",
    "photo.png": "not really a png",
    "notes_template.md": "fill me in",
    "mystery.xyz": "???",
}

@pytest.fixture()
def folder(tmp_path):
    for n, t in FILES.items():
        (tmp_path / n).write_text(t, encoding="utf-8")
    return tmp_path

def snap(root):
    return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime) for p in root.iterdir()}

def test_contract_vocab_readonly(folder):
    before = snap(folder)
    recs = run.run_lexicon(sorted(folder.iterdir()))
    assert snap(folder) == before, "lexicon engine modified files"
    schema = json.loads((ROOT / "shared/contracts/classification.v1.schema.json").read_text())
    tax = json.loads((APP / "lexicon/classification_2_0.json").read_text(encoding="utf-8"))["axes"]
    assert len(recs) == len(FILES)
    for r in recs:
        for k in schema["required"]:
            assert k in r, (k, r["source_path"])
        assert len(r["sha256"]) == 64 and r["schema_version"] == "classification.v1"
        for l in r["labels"]:
            assert 0 <= l["confidence"] <= 1
        assert r["physical_home"] in tax["physical_home"]["values"]
        assert r["document_type"] in tax["document_type"]["values"]
        assert r["chi_primary"] in tax["chi_primary"]["values"]
        assert r["lifecycle"] in tax["lifecycle"]["values"]
        assert r["epistemic_roles"] and r["subject_domains"]  # R4: never empty
    by = {Path(r["source_path"]).name: r for r in recs}
    assert by["tool.py"]["physical_home"] == "80_SYSTEM" and by["tool.py"]["document_type"] == "code"
    assert by["photo.png"]["physical_home"] == "60_MEDIA_DATA"
    assert by["notes_template.md"]["document_type"] == "template"
    assert by["mystery.xyz"]["physical_home"] == "99_REVIEW"
    g = by["gravity_paper.md"]
    assert g["chi_primary"] == "G" and "gravity" in g["matched_terms"]

def test_frontmatter_override_and_blind(folder):
    stamped = [folder / "stamped.md"]
    r = run.run_lexicon(stamped)[0]
    assert r["chi_primary"] == "E" and r["document_type"] == "series_paper" and "from_frontmatter" in r["flags"]
    assert r["canon_status"] == "admitted"  # David's recorded ruling is carried, not invented
    blind = run.run_lexicon(stamped, ignore_frontmatter=True)[0]
    assert blind["chi_primary"] == "G"  # body vocabulary only
    assert blind["canon_status"] != "admitted"  # R3

def test_deterministic(folder):
    a = run.run_lexicon(sorted(folder.iterdir()))
    b = run.run_lexicon(sorted(folder.iterdir()))
    strip = lambda rs: [{k: v for k, v in r.items() if k != "created_at"} for r in rs]
    assert strip(a) == strip(b)
