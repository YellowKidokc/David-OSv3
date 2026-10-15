import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "03_CLASSIFY" / "03_RENAMING"))
import rename_engine as eng  # noqa: E402


def _proposal(p: Path, final: str) -> "eng.Proposal":
    # apply() re-verifies the scan-time hash before renaming, so proposals must carry it
    return eng.Proposal(path=p, proposed=final, confidence=0.99,
                        sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def test_apply_refuses_batch_containing_env(tmp_path):
    secret = tmp_path / ".env"
    secret.write_text("API_KEY=x", encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("hi", encoding="utf-8")
    rows = [
        (_proposal(secret, "renamed.env"), "renamed.env", "rename"),
        (_proposal(notes, "renamed.md"), "renamed.md", "rename"),
    ]
    run_id, count, errors = eng.apply(tmp_path, rows)
    assert count == 0
    assert errors and any("GR-004" in e for e in errors)
    assert secret.read_text(encoding="utf-8") == "API_KEY=x"   # untouched
    assert notes.read_text(encoding="utf-8") == "hi"            # nothing in batch moved


def test_apply_clean_batch_still_works(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    rows = [(_proposal(f, "b.md"), "b.md", "rename")]
    run_id, count, errors = eng.apply(tmp_path, rows)
    assert count == 1 and (tmp_path / "b.md").exists()
