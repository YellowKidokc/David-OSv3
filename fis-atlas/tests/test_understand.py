from fis.understand import LexiconComprehender, purpose_sentence


def test_recognizes_theophysics_and_signals():
    c = LexiconComprehender()
    blob = ("The Master Equation governs the chi field. We derive the Lagrangian "
            "and map Law 01 through the Ten Laws. Therefore coherence follows.")
    comp = c.comprehend(blob)
    assert "theophysics" in comp.domains
    assert "governing_equation" in comp.signals or "derivation" in comp.signals
    assert comp.confidence > 0


def test_plain_text_has_no_domain():
    c = LexiconComprehender()
    comp = c.comprehend("grocery list: milk eggs bread")
    assert comp.domains == []
    assert comp.confidence == 0


def test_purpose_sentence_uses_domains():
    c = LexiconComprehender()
    comp = c.comprehend("master equation derivation lagrangian ten laws chi field")
    s = purpose_sentence("research", comp, 12)
    assert "theophysics" in s and "12 items" in s
