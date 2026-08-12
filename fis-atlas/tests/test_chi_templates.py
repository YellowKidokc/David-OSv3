import tempfile
from pathlib import Path

from fis import chi, templates
from fis.engine import Operation


# ---- chi Level-2 classifier ----
def test_chi_rates_ten_factors_and_picks_primary():
    r = chi.classify("K__LOGOS.md", "Logos information Shannon knowledge equations definitions proof")
    assert r.primary_factor == "K"
    assert r.scores["K"] >= 2
    assert len(r.vector()) >= 20        # G0M0... all ten present


def test_chi_proposes_meqs_filename_but_never_auto_renames():
    r = chi.classify("random_notes.md", "master equation coherence integration christ")
    assert r.suggested_filename.startswith(r.primary_factor + "__")
    assert r.suggested_filename.endswith(".md")
    assert r.rename_allowed is False    # supervised — suggestion only


def test_chi_uses_entity_registry_for_names():
    entities = {"LOGOS_PRINCIPLE": {"aliases": ["The Logos Principle", "Paper 01"]}}
    r = chi.classify("paper01.md", "This is The Logos Principle about information", entities=entities)
    assert r.entity_guess == "LOGOS_PRINCIPLE"   # alias resolved, not drifted


def test_chi_state_guess_unknown_when_ambiguous():
    assert chi.classify("draft_thing.md", "").state_guess == "W"
    assert chi.classify("thing.md", "").state_guess == "U"


# ---- job template (fill-in-the-blanks) ----
def test_template_instantiates_a_filejob():
    d1, d2 = tempfile.mkdtemp(), tempfile.mkdtemp()
    job = templates.build("aggregation", roots=[d1, d2], destination="O:/GTQ",
                          concept="Genesis to Quantum")
    assert job.destination == "O:/GTQ"
    assert job.roots == [d1, d2]
    assert Operation.DEDUPLICATE in job.operations
    assert job.apply is False and job.approved is False    # safe defaults
    assert "GTQ" in job.aliases or "Genesis to Quantum" in job.aliases


def test_template_override_aliases():
    job = templates.build("aggregation", roots=["X"], destination="Y",
                          concept="Invoices", aliases=["invoice", "receipt", "bill"])
    assert "receipt" in job.aliases
    assert job.name == "Aggregate Invoices"
