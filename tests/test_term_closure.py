import csv, json

def test_closure_groups_duplicates_and_proposes_one_keeper(tmp_path):
    from engine.term_closure import plan_closure
    source = tmp_path / "source"; output = tmp_path / "output"
    (source / "Canon").mkdir(parents=True); (source / "Backup").mkdir()
    gold = "Master Equation canonical derivation evidence"
    (source / "Canon" / "master-equation.md").write_text(gold, encoding="utf-8")
    (source / "Backup" / "copy.md").write_text(gold, encoding="utf-8")
    (source / "notes.md").write_text("A passing note about master equation", encoding="utf-8")
    (source / "unrelated.md").write_text("gardening", encoding="utf-8")
    summary = plan_closure([source], output, "Master Equation", ["master-equation"])
    assert summary["candidate_instances"] == 3 and summary["unique_content_objects"] == 2
    assert summary["duplicate_groups"] == 1 and summary["extra_duplicate_locations"] == 1
    rows = list(csv.DictReader((output / "closure_plan.csv").open(encoding="utf-8-sig")))
    groups = {}
    for row in rows: groups.setdefault(row["sha256"], []).append(row)
    dup = next(g for g in groups.values() if len(g) == 2)
    assert sum(r["proposed_keeper"] == "True" for r in dup) == 1
    assert "HUMAN_APPROVED" in next(r for r in dup if r["proposed_keeper"] == "False")["deletion_eligibility"]
    assert json.loads((output / "summary.json").read_text(encoding="utf-8"))["mode"].startswith("observe")

def test_closure_output_must_be_outside_sources(tmp_path):
    import pytest
    from engine.term_closure import plan_closure
    source = tmp_path / "source"; source.mkdir()
    with pytest.raises(ValueError, match="outside"): plan_closure([source], source / "out", "Logos")
