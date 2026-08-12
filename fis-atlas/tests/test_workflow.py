import tempfile
from pathlib import Path

from fis import workflow


def _drives():
    """Two fake 'drives' with GTQ files scattered in subfolders, plus noise."""
    d1 = Path(tempfile.mkdtemp()); d2 = Path(tempfile.mkdtemp())
    (d1 / "a").mkdir(); (d1 / "a" / "b").mkdir(); (d2 / "x").mkdir()
    # strong GTQ matches (in different folders/depths)
    (d1 / "a" / "GTQ_intro.md").write_text("Genesis to Quantum: GTQ series part 1. genesis quantum.")
    (d1 / "a" / "b" / "gtq_part2.md").write_text("GTQ continues. Genesis to Quantum framework.")
    (d2 / "x" / "quantum_genesis_notes.md").write_text("genesis to quantum notes, quantum genesis.")
    # an exact duplicate of intro on the other drive
    (d2 / "GTQ_intro_copy.md").write_text("Genesis to Quantum: GTQ series part 1. genesis quantum.")
    # borderline (only 'quantum')
    (d1 / "quantum_computing.md").write_text("A note about quantum computing hardware.")
    # noise
    (d2 / "grocery.md").write_text("milk eggs bread")
    return [str(d1), str(d2)]


def test_finds_gtq_across_drives():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ")
    assert plan.summary["in_range"] >= 3          # the three strong GTQ files
    assert plan.summary["out_of_range"] >= 1      # quantum_computing.md


def test_flatten_avoids_name_collision():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ")
    tos = [p["to"] for p in plan.proposals if p["action"] == "aggregate_flatten"]
    assert len(tos) == len(set(tos))              # no two files flattened to same path


def test_dedupe_quarantines_the_copy():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ")
    assert plan.summary["duplicates_to_quarantine"] >= 1
    assert any(p["action"] == "quarantine_duplicate" for p in plan.proposals)


def test_asks_the_one_categorization_question():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ")   # mode not given
    q = [q for q in plan.questions if q["question_id"] == "Q-GTQ-CAT"]
    assert q and "extension" in " ".join(q[0]["options"]).lower()


def test_out_of_range_becomes_a_question():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ")
    assert any(q["question_id"] == "Q-GTQ-RANGE" for q in plan.questions)


def test_answering_mode_skips_the_question_and_buckets():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ", categorize_mode="extension")
    assert not any(q["question_id"] == "Q-GTQ-CAT" for q in plan.questions)
    assert any(p["action"] == "categorize" for p in plan.proposals)


def test_nothing_mutates():
    plan = workflow.run_gtq_aggregation(_drives(), target="C:/GTQ")
    assert plan.summary["mutations"] == 0
