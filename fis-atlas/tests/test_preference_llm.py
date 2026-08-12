import tempfile
from pathlib import Path

from fis.preference import Preferences
from fis import llm


def _prefs():
    return Preferences(Path(tempfile.mkdtemp()) / "prefs.db")


def test_contextual_counts_learn_best_target():
    p = _prefs()
    # research markdown: approved to Papers 31x, to Archive rejected 18x
    for _ in range(31):
        p.record("markdown", "research", "move", "Papers", approved=True)
    for _ in range(18):
        p.record("markdown", "research", "move", "Archive", approved=False)
    for _ in range(3):
        p.record("markdown", "research", "move", "Archive", approved=True)
    best, rate = p.best_target("markdown", "research", "move")
    assert best == "Papers"
    assert rate > 0.9
    # Archive got mostly rejected -> low rate
    assert p.approval_rate("markdown", "research", "move", "Archive") < 0.3
    p.close()


def test_smoothing_handles_unseen():
    p = _prefs()
    # never seen -> neutral 0.5 (1/2), not a crash or 0
    assert p.approval_rate("image", "downloads", "move", "Media") == 0.5
    p.close()


def test_markov_on_approvals_predicts_next_action():
    p = _prefs()
    for _ in range(5):
        p.record_action_sequence("scan", "classify")
    p.record_action_sequence("scan", "report")
    assert p.predict_next_action("scan") == "classify"
    p.close()


def test_name_style_learns_from_approved_names():
    p = _prefs()
    for nm in ["TH_DOC_grace_thermodynamics.md", "TH_DOC_entropy_covenant.md",
               "TH_DOC_chi_field_notes.md"]:
        p.learn_approved_name(nm)
    on_style = p.name_style_score("TH_DOC_new_topic.md")
    off_style = p.name_style_score("random garbage file.md")
    assert on_style > off_style
    p.close()


def test_ollama_seam_degrades_gracefully_when_absent():
    # No Ollama in CI -> phrase_question must still return a valid deterministic question.
    res = llm.phrase_question("Which file governs?", "multiple_authority_claims",
                              ["paper_FINAL.md", "paper_SOURCE_OF_TRUTH.md"],
                              ["which_is_authoritative", "show_examples"])
    assert res["text"] == "Which file governs?"
    assert res["source"] in ("deterministic", "ollama")
