from fis import visual, corpus_learn


def test_calibrate_recommends_from_measured_distances():
    # same pictures differ by small distances; different by large
    cal = visual.calibrate(same_pairs=[(0xFFFF0000, 0xFFFF0001), (0xFFFF0000, 0xFFFF0003)],
                           diff_pairs=[(0x0, 0xFFFFFFFF)])
    assert cal["same_max"] == 2                 # measured, not guessed
    assert cal["separable"] is True
    assert cal["recommended_threshold"] == 3    # just above the largest same-distance


def test_calibrate_flags_non_separable():
    cal = visual.calibrate(same_pairs=[(0x0, 0xFFFF)],       # "same" but 16 apart
                           diff_pairs=[(0x0, 0xFF)])          # "diff" but only 8 apart
    assert cal["separable"] is False and cal["recommended_threshold"] is None


def test_aperture_sweep_shows_change_across_windows():
    # 'mercy' sits next to justice; 'faraway' sits ~15 tokens off and repeats
    docs = ["justice mercy atonement " + "filler " * 12 + "faraway aa faraway",
            "justice mercy again " + "filler " * 12 + "faraway bb faraway"]
    sweep = corpus_learn.aperture_sweep(["justice"], docs, windows=(2, 30), top=10)
    tight = {t[0] for t in sweep[2]}
    wide = {t[0] for t in sweep[30]}
    assert "mercy" in tight
    assert "faraway" in wide and "faraway" not in tight      # only the open aperture reaches it
