from fis import corpus_learn

CORPUS = [
    "justice and mercy meet at the cross where atonement pays the debt in full.",
    "the demand for justice is answered by mercy; atonement satisfies the judgment.",
    "unrelated weather report about clouds and traffic far from any theology topic.",
]


def test_windowed_association_reports_distance():
    assoc = corpus_learn.windowed_associations(["justice"], CORPUS, window=8, min_count=2)
    terms = {a.term: a for a in assoc}
    assert "mercy" in terms and "atonement" in terms
    assert terms["mercy"].avg_distance > 0            # measured words-from-seed
    assert "weather" not in terms and "traffic" not in terms


def test_aperture_closes_to_only_nearby_words():
    seed_near = ["justice and mercy right next to each other and far off atonement " +
                 "word " * 20 + "atonement"]
    tight = {a.term for a in corpus_learn.windowed_associations(["justice"], seed_near, window=2, min_count=1)}
    wide = {a.term for a in corpus_learn.windowed_associations(["justice"], seed_near, window=30, min_count=1)}
    assert "mercy" in tight                            # immediate neighbor survives the tight aperture
    assert "atonement" in wide and "atonement" not in tight   # far word only at open aperture


def test_aperture_levels():
    assert corpus_learn.aperture_window("tight") < corpus_learn.aperture_window("normal")
    assert corpus_learn.aperture_window("wide") < corpus_learn.aperture_window("open")


def test_classifier_seed_has_categories():
    from fis import classifier_seed
    lex = classifier_seed.seed_lexicon()
    assert "WISDOM" in lex and "FRUIT_love" in lex and "ME_C_christ_coherence" in lex
    assert "logos" in lex["WISDOM"] and "christ" in lex["ME_C_christ_coherence"]
