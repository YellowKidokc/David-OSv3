from fis import opmap


def test_every_family_is_present():
    codes = opmap.scan()
    for fam in ("lok", "idn", "und", "sim", "dec", "gov", "lrn", "aut"):
        assert fam in codes, f"no module tagged {fam}"


def test_known_modules_carry_expected_codes():
    codes = opmap.scan()
    assert any("scan.py" in m for m in codes["lok"])
    assert any("match.py" in m for m in codes["sim"])
    assert any("chi.py" in m for m in codes["und"])
    assert any("lineage.py" in m for m in codes["idn"])
    assert any("preference.py" in m for m in codes["lrn"])
    assert any("node_agent.py" in m for m in codes["aut"])


def test_manifest_lists_handlers_and_counts():
    man = opmap.manifest()
    assert man["total_modules"] >= 20
    assert "sim/dedupe" in man["handlers"]
    assert man["counts"].get("gov", 0) >= 3


def test_by_code_returns_only_that_family():
    dec = opmap.by_code("dec")
    assert dec and all(m.endswith(".py") for m in dec)
