import csv
import json
import sqlite3


def test_intake_preserves_instances_groups_content_and_flags(tmp_path):
    from engine.master_equation_intake import analyze

    source = tmp_path / "source"
    output = tmp_path / "output"
    (source / "Canon").mkdir(parents=True)
    (source / "_H_DESKTOP_INTAKE_2026-08-24").mkdir()
    text = "Master Equation grace gravity Logos Shannon coherence Christ derivation"
    (source / "Canon" / "MASTER_EQUATION.md").write_text(text, encoding="utf-8")
    (source / "_H_DESKTOP_INTAKE_2026-08-24" / "copy.md").write_text(text, encoding="utf-8")
    (source / "bad_onlyfans_setup.exe").write_bytes(b"foreign")

    summary = analyze(source, output)

    assert summary["file_instances"] == 3
    assert summary["unique_content_objects"] == 2
    assert summary["exact_duplicate_groups"] == 1
    assert summary["extra_duplicate_locations"] == 1
    assert summary["contamination_flagged"] == 1
    assert summary["variable_coverage"]["G"] == 2
    assert summary["variable_coverage"]["K"] == 2
    assert summary["variable_coverage"]["C_W"] == 2

    con = sqlite3.connect(output / "master_equation_intake.sqlite")
    try:
        assert con.execute("select count(*) from file_instances").fetchone()[0] == 3
        assert con.execute("select count(*) from content_objects").fetchone()[0] == 2
    finally:
        con.close()

    with (output / "exact_duplicate_groups.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["source_lane"] for row in rows} == {"canon", "intake"}
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["mode"] == "observe_only_no_source_mutation"


def test_output_inside_source_is_rejected(tmp_path):
    import pytest
    from engine.master_equation_intake import analyze

    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="outside"):
        analyze(source, source / "generated")

