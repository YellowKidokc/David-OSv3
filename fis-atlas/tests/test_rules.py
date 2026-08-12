from fis import rules as R
from fis.model import ObjectRecord


def _o(**kw):
    base = dict(object_id="O", name="x", ext="", full_path="C:/x", is_dir=False)
    base.update(kw)
    return ObjectRecord(**base)


def test_parse_and_match():
    rules = R.parse_rules("WHEN content_type is image THEN move = Media/Unsorted")
    assert len(rules) == 1
    o = _o(content_type="image")
    assert rules[0].matches(o)


def test_apply_sets_treatment_and_dest():
    rules = R.parse_rules("WHEN content_type is archive THEN archive = _Archives")
    o = _o(content_type="archive", authorized_actions=["archive"], forbidden_actions=[])
    objs = {"O": o}
    R.apply_rules(objs, rules)
    assert o.proposed_treatment == "archive" and o.probable_destination == "_Archives"


def test_rule_cannot_override_forbidden_action():
    rules = R.parse_rules("WHEN content_type is code THEN move = elsewhere")
    o = _o(content_type="code", forbidden_actions=["move"], proposed_treatment="protect")
    R.apply_rules({"O": o}, rules)
    assert o.proposed_treatment == "protect"   # fail closed


def test_and_conditions():
    rules = R.parse_rules('WHEN content_type is image AND name matches screenshot THEN move = M')
    assert rules[0].matches(_o(content_type="image", name="Screenshot_1.png"))
    assert not rules[0].matches(_o(content_type="image", name="photo.png"))


def test_normalize_handler():
    from fis.handlers import dec_normalize
    assert dec_normalize.propose("My File (3).MD") == "my_file_3.md"
    assert dec_normalize.propose("teh seperate fisics.txt") == "the_separate_physics.txt"
