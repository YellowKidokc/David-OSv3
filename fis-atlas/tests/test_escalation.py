import tempfile
from pathlib import Path

import pytest

from fis.escalation import Escalation
from fis import llm


def _esc():
    return Escalation(Path(tempfile.mkdtemp()) / "esc.db", max_self_serve=3)


def test_model_not_available_until_three_unresolved():
    e = _esc()
    key = "folder:X:authority"
    assert not e.should_engage_model(key)
    e.note_attempt(key, "dec_rules", resolved=False)
    e.note_attempt(key, "manual_move", resolved=False)
    assert not e.should_engage_model(key)          # only 2 tries
    e.note_attempt(key, "manual_move", resolved=False)
    assert e.should_engage_model(key)              # 3rd unresolved -> model may talk
    e.close()


def test_resolution_resets_the_counter():
    e = _esc()
    key = "folder:Y:rename"
    for _ in range(3):
        e.note_attempt(key, "dec_rules", resolved=False)
    assert e.should_engage_model(key)
    e.note_attempt(key, "dec_rules", resolved=True)   # solved it
    assert not e.should_engage_model(key)             # back to self-serve
    e.close()


def test_state_reports_remaining():
    e = _esc()
    key = "k"
    e.note_attempt(key, "t", resolved=False)
    s = e.state(key)
    assert s["remaining_before_model"] == 2 and not s["model_available"]
    e.close()


def test_capability_contract_allows_wording_denies_actions():
    llm.enforce("select_question_template")        # allowed, no raise
    llm.enforce("phrase_question")
    for forbidden in ("invent_policy", "execute_action", "move_file",
                      "decide_authority", "promote_canonical", "totally_unknown"):
        with pytest.raises(llm.CapabilityError):
            llm.enforce(forbidden)
