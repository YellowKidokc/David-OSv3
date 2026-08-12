import tempfile
from pathlib import Path

import pytest

from fis import engine
from fis.engine import Operation, State

# temp dirs OUTSIDE AppData (the engine correctly seals anything under AppData)
_BASE = Path("_test_tmp").resolve()
_BASE.mkdir(exist_ok=True)


def _mkdtemp():
    return tempfile.mkdtemp(dir=str(_BASE))


def _corpus():
    """Two 'drives' with scattered GTQ files, a dup, a protected file, noise."""
    d1 = Path(_mkdtemp()); d2 = Path(_mkdtemp())
    (d1 / "a").mkdir()
    (d1 / "a" / "GTQ_law01.md").write_text("Genesis to Quantum law 01")
    (d1 / "gtq_law02.md").write_text("GTQ law 02 Genesis to Quantum")
    (d2 / "GTQ_law01_copy.md").write_text("Genesis to Quantum law 01")   # exact dup of law01
    (d2 / ".env").write_text("SECRET_KEY=abc")                           # protected
    (d2 / "grocery.md").write_text("milk eggs")                          # noise
    dest = Path(_mkdtemp()) / "GTQ_AGGREGATE"
    return [str(d1), str(d2)], str(dest)


def test_preview_finds_members_and_never_mutates():
    roots, dest = _corpus()
    job = engine.gtq_job(roots, dest)              # apply=False by default
    res = engine.run_file_job(job)
    assert res.summary["accepted"] >= 2
    assert res.executed == 0
    assert not Path(dest).exists() or not any(Path(dest).rglob("*.md"))  # nothing copied


def test_protected_file_excluded():
    roots, dest = _corpus()
    res = engine.run_file_job(engine.gtq_job(roots, dest))
    env = [r for r in res.records if r.name == ".env"][0]
    assert env.protected and env.role == "protected"
    assert not any(a.source.endswith(".env") for a in res.actions)


def test_exact_duplicate_collapsed_in_aggregate():
    roots, dest = _corpus()
    res = engine.run_file_job(engine.gtq_job(roots, dest))
    law01_targets = [a for a in res.actions if "law01" in a.source.lower()]
    # two law01 files on disk, but only ONE copied into the aggregate
    assert len(law01_targets) == 1
    assert res.summary["exact_duplicate_groups"] >= 1


def test_corroboration_boosts_ownership():
    roots, dest = _corpus()
    res = engine.run_file_job(engine.gtq_job(roots, dest))
    law01 = [r for r in res.records if "law01" in r.name.lower()]
    assert any(r.ownership_prob >= r.membership_score for r in law01)   # seen in 2 folders


def test_execution_blocked_without_approval():
    roots, dest = _corpus()
    job = engine.gtq_job(roots, dest, apply=True)   # apply on, but approved=False
    res = engine.run_file_job(job)
    assert res.executed == 0                          # gate 2 (approved) stops it


def test_real_execution_copies_verifies_preserves_and_rolls_back():
    roots, dest = _corpus()
    job = engine.gtq_job(roots, dest, apply=True, approved=True)
    res = engine.run_file_job(job)
    assert res.executed >= 2 and res.failed == 0
    # files actually copied into the aggregate
    assert list(Path(dest).rglob("*.md"))
    # originals still there (copy, not move)
    assert (Path(roots[0]) / "gtq_law02.md").exists()
    # rollback manifest + ledger written
    assert (Path(dest) / ".fis-rollback.json").exists()
    assert (Path(dest) / ".fis-ledger.jsonl").exists()
    # every executed action verified by hash (no failures)
    assert all(a.state == State.EXECUTED for a in res.actions if a.authorized)
