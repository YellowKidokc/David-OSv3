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
    run_id, count, errors = eng.apply(tmp_path, rows, override=True)  # user approved in the dialog
    assert count == 1 and (tmp_path / "b.md").exists()


def test_apply_ask_batch_requires_explicit_override(tmp_path):
    # no profile on tmp_path -> action default floor (approval_required) -> ASK;
    # the engine is the last line of defense and must not run ASK batches blind
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    rows = [(_proposal(f, "b.md"), "b.md", "rename")]
    run_id, count, errors = eng.apply(tmp_path, rows)
    assert count == 0 and not (tmp_path / "b.md").exists()
    assert errors and any("approval" in e.lower() for e in errors)
    run_id, count, errors = eng.apply(tmp_path, rows, override=True)
    assert count == 1 and (tmp_path / "b.md").exists()


def test_corrupt_profile_registry_fails_closed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ValueError("corrupt json")
    monkeypatch.setattr(eng._Profiles, "load", boom)
    f = tmp_path / "a.md"
    f.write_text("x", encoding="utf-8")
    rows = [(_proposal(f, "b.md"), "b.md", "rename")]
    # corrupt registry -> ASK-everything -> no blind rename
    run_id, count, errors = eng.apply(tmp_path, rows)
    assert count == 0 and not (tmp_path / "b.md").exists()
    assert errors and any("load error" in e.lower() for e in errors)
    # the error is visible in the fired rules, and a human override may still proceed
    run_id, count, errors = eng.apply(tmp_path, rows, override=True)
    assert count == 1 and (tmp_path / "b.md").exists()
