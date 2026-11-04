from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from engine import registry
from engine.me_rename_bridge import add_name_context, read_intake
from engine.rename_applier import apply, plan, simulate, undo
from engine.sidecar_writer import generate


def _registry(tmp_path: Path, source: Path, *, lane: str = "READY") -> Path:
    db = tmp_path / "registry.sqlite"
    con = registry.connect(db)
    digest = registry.sha256_file(str(source))
    timestamp = registry.now()
    con.execute(
        "INSERT INTO series VALUES(?,?,?,?,?,?,?)",
        ("TST", str(source.parent), "Tests", "[]", "proposed", registry.TOOL, registry.RULEBOOK),
    )
    con.execute(
        """INSERT INTO works(work_id,series_code,display_code,preferred_title,aliases_json,
                              tool_version,rulebook_version)
           VALUES(?,?,?,?,?,?,?)""",
        ("W000001", "TST", "TST-001", "Grace proof", "[]", registry.TOOL, registry.RULEBOOK),
    )
    con.execute(
        "INSERT INTO versions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("V1", "W000001", digest, digest, None, None, json.dumps([str(source)]),
         "proposed", timestamp, registry.TOOL, registry.RULEBOOK),
    )
    con.execute(
        """INSERT INTO nabla(version_id,work_id,address,protocol_version,source_sha256,
                              tool_version,rulebook_version,status)
           VALUES(?,?,?,?,?,?,?,?)""",
        ("V1", "W000001", "SELF/TH/ACTIVE", registry.PROTOCOL, digest,
         registry.TOOL, registry.RULEBOOK, "proposed"),
    )
    stat = source.stat()
    con.execute(
        """INSERT INTO files(path,root,drive,size,mtime_ns,sha256,text_sha256,extension,
                             readable,extraction_error,extraction_method,normalization,
                             observed_title,version_id,first_seen,last_seen,present,
                             tool_version,rulebook_version)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(source), str(source.parent), source.drive, stat.st_size, stat.st_mtime_ns,
         digest, digest, source.suffix, "yes", None, "test", "none", "Grace proof",
         "V1", timestamp, timestamp, 1, registry.TOOL, registry.RULEBOOK),
    )
    con.execute(
        """CREATE TABLE admission(
               source_path TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL,
               lane TEXT NOT NULL, family_id TEXT, family_relation TEXT,
               is_representative INTEGER, representative_sha256 TEXT,
               reason_codes TEXT, decision_authority TEXT, decision_version TEXT
           )"""
    )
    con.execute(
        "INSERT INTO admission VALUES(?,?,?,?,?,?,?,?,?,?)",
        (str(source), digest, lane, "F1", "unique", 1, digest,
         json.dumps(["READY_READABLE_PERMITTED"]), "deterministic_rule", "admission-rules/v1"),
    )
    con.commit()
    con.close()
    return db


def test_sidecar_writer_requires_admission(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text("# Grace\nA proof about grace.", encoding="utf-8")
    db = _registry(tmp_path, source)
    with sqlite3.connect(db) as con:
        con.execute("DROP TABLE admission")
        con.commit()
    with pytest.raises(ValueError, match="admission table"):
        generate(tmp_path, db_path=db, dry_run=True)


def test_sidecar_writer_is_incremental_and_preserves_human_override(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text("# Grace\nA theorem and proof about grace and coherence.", encoding="utf-8")
    db = _registry(tmp_path, source)

    preview = generate(tmp_path, db_path=db, dry_run=True)
    assert preview["files_processed"] == 1
    assert not Path(str(source) + ".fis.json").exists()

    first = generate(tmp_path, db_path=db)
    assert first["sidecars_created"] == 1
    sidecar = Path(str(source) + ".fis.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["work_id"] == "W000001"
    assert payload["admission"]["lane"] == "READY"
    assert payload["rename_approved"] is False

    second = generate(tmp_path, db_path=db)
    assert second["unchanged_skipped"] == 1

    payload["domain"] = "HUMAN"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with sqlite3.connect(db) as con:
        con.execute("UPDATE admission SET decision_version='admission-rules/v2'")
        con.commit()
    forced_refresh = generate(tmp_path, db_path=db, force=False)
    assert forced_refresh["sidecars_updated"] == 1
    assert json.loads(sidecar.read_text(encoding="utf-8"))["domain"] == "HUMAN"


def test_rename_apply_and_conflict_safe_undo(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text("# Grace\nA theorem and proof about grace.", encoding="utf-8")
    db = _registry(tmp_path, source)
    generate(tmp_path, db_path=db)
    sidecar = Path(str(source) + ".fis.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["rename_approved"] = True
    payload["proposed_name"] = "TH__PAP__GRC-PRF__20261103__AC.md"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    items = plan(tmp_path)
    assert len(items) == 1 and items[0]["eligible"] is True
    with pytest.raises(ValueError, match="--confirm"):
        apply(tmp_path, db_path=db)

    plan_file = tmp_path / "rename-simulation.json"
    simulation = simulate(tmp_path, plan_file)
    assert simulation["summary"]["eligible"] == 1
    result = apply(tmp_path, db_path=db, confirm=True, simulation=plan_file)
    assert result["approved_plan_hash"] == simulation["plan_hash"]
    assert len(result["renamed"]) == 1
    renamed = Path(result["renamed"][0]["new_path"])
    assert renamed.exists() and not source.exists()
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT path FROM files").fetchone()[0] == str(renamed)
        assert con.execute("SELECT source_path FROM admission").fetchone()[0] == str(renamed)

    restored = undo(result["changeset_id"], db_path=db)
    assert len(restored["restored"]) == 1
    assert source.exists() and not renamed.exists()


def test_apply_refuses_stale_simulation(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text("# Grace", encoding="utf-8")
    db = _registry(tmp_path, source)
    generate(tmp_path, db_path=db)
    sidecar = Path(str(source) + ".fis.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["rename_approved"] = True
    payload["proposed_name"] = "TH__DOC__GRC__20261103__AC.md"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    plan_file = tmp_path / "rename-simulation.json"
    simulate(tmp_path, plan_file)
    payload["proposed_name"] = "TH__DOC__CHANGED__20261103__AC.md"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        apply(tmp_path, db_path=db, confirm=True, simulation=plan_file)


def test_hold_is_never_rename_eligible(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text("# Hold", encoding="utf-8")
    db = _registry(tmp_path, source, lane="HOLD")
    generate(tmp_path, db_path=db)
    sidecar = Path(str(source) + ".fis.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["rename_approved"] = True
    payload["proposed_name"] = "TH__DOC__GRC__20261103__AC.md"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    assert plan(tmp_path)[0]["eligible"] is False
    assert "HOLD" in plan(tmp_path)[0]["reason"]


def test_changed_source_hash_is_never_rename_eligible(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text("# Original", encoding="utf-8")
    db = _registry(tmp_path, source)
    generate(tmp_path, db_path=db)
    sidecar = Path(str(source) + ".fis.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["rename_approved"] = True
    payload["proposed_name"] = "TH__DOC__GRC__20261103__AC.md"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    source.write_text("# Changed after review", encoding="utf-8")
    item = plan(tmp_path)[0]
    assert item["eligible"] is False
    assert "hash changed" in item["reason"]


def test_me_bridge_reads_intake_and_adds_name_context(tmp_path: Path):
    source = tmp_path / "me.md"
    source.write_text("ME", encoding="utf-8")
    db = tmp_path / "me.sqlite"
    with sqlite3.connect(db) as con:
        con.execute(
            """CREATE TABLE file_instances(
                   source_path TEXT, meq_variables_json TEXT, source_lane TEXT,
                   contamination_flags_json TEXT
               )"""
        )
        con.execute(
            "INSERT INTO file_instances VALUES(?,?,?,?)",
            (str(source), json.dumps(["E", "K"]), "derivation", json.dumps([])),
        )
    result = read_intake(db, source)
    assert result["me_variables"] == [3, 6]
    assert result["me_primary"] == 3
    assert add_name_context("PH__DOC__KNW__20261103__AC.md", 3) == "PH__DOC__me3-KNW__20261103__AC.md"

