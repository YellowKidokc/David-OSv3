import json, sqlite3, sys
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import identity as I  # noqa: E402


def test_examples_parse():
    for x in ["MEQU.01.GRACE", "MEQU.00.CANON77", "JREV.89.AUTHORITY", "JREV.95.CONCORDANCE", "DLAY.05.WATER", "LAND.01.BOUNDARY"]:
        I.parse_document_id(x)
    assert I.parse_document_id("JREV.89.AUTHORITY")["kind"] == "companion"
    assert I.parse_document_id("JREV.95.CONCORDANCE")["kind"] == "concordance"
    for bad in ["MEQU.1.GRACE", "ME.01.GRACE", "MEQU.01.grace", "MEQUXX.01.A", "MEQU-01-GRACE"]:
        with pytest.raises(ValueError):
            I.parse_document_id(bad)


def test_artifact_refs():
    assert I.parse_artifact_ref("DLAY.05.WATER::classify.105::v2")["run"] == "v2"
    assert I.parse_artifact_ref("DLAY.05.WATER::audit::2026-11-06")["role"] == "audit"
    with pytest.raises(ValueError):
        I.parse_artifact_ref("DLAY.05.WATER::made.up")


def sidecar(**over):
    sc = {"schema_version": "sidecar.v1", "document_id": "DLAY.05.WATER", "version": 2, "content_sha256": "a" * 64,
          "physical": {"current_home": "50_PRODUCTION_AND_PUBLICATION/05_SERIES_AND_ARGUMENT_CHAINS", "proposed_home": None, "move_authorized": False},
          "canonical": {"build": "MASTER_EQUATION", "law_ids": ["LAW_04", "LAW_10"], "epistemic_roles": ["bridge", "claim"],
                        "canon_status": "CANDIDATE", "admission_authority": "DAVID_ONLY"},
          "navigation": {"series_id": "DLAY", "series_position": 5, "ten_law_emphasis": {"S": 3, "C": 2}},
          "lineage": {"cross_references": [{"target": "JREV.02.WORLD", "relationship": "SOURCE_NARRATIVE_FOR"}]}}
    for k, v in over.items():
        sc[k] = {**sc[k], **v} if isinstance(v, dict) else v
    return sc


def test_sidecar_safety_rules():
    assert I.check_sidecar(sidecar()) == []
    assert any("rule 1" in e for e in I.check_sidecar(sidecar(canonical={"canon_status": "ADMITTED"})))
    ok = sidecar(canonical={"canon_status": "ADMITTED", "admitted_by_ruling": "R-1"})
    assert I.check_sidecar(ok, approved_admissions={"R-1"}) == []
    assert any("rule 5" in e for e in I.check_sidecar(sidecar(physical={"move_authorized": True})))


def test_sidecar_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((HERE / "sidecar.v1.schema.json").read_text())
    jsonschema.validate(sidecar(), schema)


def test_registry_and_triggers(tmp_path):
    con = I.build_registry(tmp_path / "r.sqlite")
    n = dict(con.execute("SELECT series_id, count(*) FROM documents GROUP BY series_id"))
    assert n == {"DLAY": 9, "JREV": 16, "MEQU": 11}
    assert con.execute("SELECT status FROM documents WHERE document_id='JREV.89.AUTHORITY'").fetchone()[0] == "displaced"
    assert con.execute("SELECT status FROM documents WHERE document_id='MEQU.07.FAITH'").fetchone()[0] == "planned"
    assert con.execute("SELECT count(*) FROM relations").fetchone()[0] == 4
    with pytest.raises(sqlite3.DatabaseError, match="permanent"):
        con.execute("UPDATE documents SET slug='OTHER' WHERE document_id='DLAY.05.WATER'")
    with pytest.raises(sqlite3.IntegrityError):  # duplicate position in a series
        con.execute("INSERT INTO documents(document_id, series_id, position, slug) VALUES ('DLAY.05.FLOOD','DLAY',5,'FLOOD')")
    with pytest.raises(sqlite3.IntegrityError):  # only David approves
        con.execute("INSERT INTO approvals(approval_id, document_id, action, approved_by) VALUES ('a','DLAY.05.WATER','admit','Claude')")
    con.execute("INSERT INTO artifacts(artifact_id, document_id, artifact_role, content_sha256) VALUES ('x','DLAY.05.WATER','audit','00')")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("UPDATE artifacts SET content_sha256='11' WHERE artifact_id='x'")
