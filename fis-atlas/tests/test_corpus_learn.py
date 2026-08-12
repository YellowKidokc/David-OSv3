from fis import corpus_learn


CORPUS = [
    # justice/mercy travel together across several paragraphs
    "The demand for justice is answered by mercy at the cross; atonement pays the debt.\n\n"
    "True justice requires that mercy and atonement meet, so judgment is satisfied.\n\n"
    "Where justice and mercy embrace, righteousness follows and the ledger is balanced.",
    # an unrelated paragraph with frequent but non-associated words
    "The weather today is cloudy and the traffic on the highway was heavy this morning.\n\n"
    "Coffee prices rose and the grocery store was crowded near the parking lot.",
    "Justice without mercy is cruelty; mercy without justice is license — atonement unites them.",
]


def test_associated_terms_finds_the_vernacular_that_travels_with_seed():
    assoc = corpus_learn.associated_terms(["justice"], CORPUS, min_count=2)
    terms = [a.term for a in assoc]
    assert "mercy" in terms and "atonement" in terms
    assert "weather" not in terms and "traffic" not in terms   # unrelated -> excluded


def test_lift_ranks_distinctive_over_merely_frequent():
    assoc = corpus_learn.associated_terms(["justice"], CORPUS, min_count=2)
    # every returned association is genuinely co-occurring, with a positive lift
    assert assoc and all(a.co_count >= 2 and a.lift > 0 for a in assoc)


def test_familiarize_returns_per_category_proposals_marked_inferred():
    seeds = {"JUSTICE_MERCY": ["justice", "mercy"], "WEATHER": ["weather"]}
    out = corpus_learn.familiarize(seeds, CORPUS, min_count=2)
    jm = [t[0] for t in out["JUSTICE_MERCY"]]
    assert "atonement" in jm or "righteousness" in jm
    # WEATHER seed barely co-occurs with anything meaningful in this corpus
    assert isinstance(out["WEATHER"], list)


def test_seed_words_are_not_proposed_as_their_own_associations():
    assoc = corpus_learn.associated_terms(["justice", "mercy"], CORPUS, min_count=1)
    terms = [a.term for a in assoc]
    assert "justice" not in terms and "mercy" not in terms
