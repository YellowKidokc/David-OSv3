import time
from fis.model import FolderRecord, ObjectRecord
from fis import classify


def _obj(name, ctype, **kw):
    return ObjectRecord(object_id="O", name=name, ext="", full_path=f"C:/x/{name}",
                        is_dir=False, parent="C:/x", content_type=ctype,
                        rel_path=kw.get("rel", name), modified=time.time(), accessed=time.time())


def test_programming_folder_is_red_and_sealed():
    f = FolderRecord(object_id="F", name="proj", full_path="C:/x/proj")
    classify.classify_folder(f, [".git", "package.json"], [])
    assert f.folder_class == "programming"
    assert f.risk == "red"
    assert "move" in f.forbidden_actions and "rename" in f.forbidden_actions


def test_code_heavy_folder_is_red_even_without_markers():
    f = FolderRecord(object_id="F", name="src", full_path="C:/x/src")
    objs = [_obj(f"a{i}.py", "code") for i in range(6)]
    classify.classify_folder(f, [o.name for o in objs], objs)
    assert f.risk == "red" and f.folder_class == "programming"


def test_media_folder_is_green():
    f = FolderRecord(object_id="F", name="pics", full_path="C:/x/pics")
    objs = [_obj(f"IMG_{i}.png", "image") for i in range(8)]
    classify.classify_folder(f, [o.name for o in objs], objs)
    assert f.risk == "green" and f.folder_class == "media"


def test_secret_object_is_red_regardless_of_folder():
    f = FolderRecord(object_id="F", name="cfg", full_path="C:/x/cfg", risk="green",
                     allowed_actions=["rename"], forbidden_actions=[])
    o = _obj(".env", "unknown", rel="cfg/.env")
    classify.classify_object(o, f)
    assert o.risk == "red" and o.proposed_treatment == "protect"
    assert "move" in o.forbidden_actions


def test_certainty_and_authorization_are_separate():
    # high class confidence but red -> still not authorized to move
    f = FolderRecord(object_id="F", name="proj", full_path="C:/x/proj")
    classify.classify_folder(f, [".git"], [])
    o = _obj("main.py", "code", rel="proj/main.py")
    classify.classify_object(o, f)
    assert o.class_confidence >= 0.8          # sure what it is
    assert "move" in o.forbidden_actions       # but not allowed to move it


def test_ancestral_context_sets_financial():
    f = FolderRecord(object_id="F", name="2025", full_path="C:/Taxes/2025", risk="green",
                     allowed_actions=["rename"], forbidden_actions=[])
    o = _obj("notes.md", "markdown", rel="Taxes/2025/notes.md")
    classify.classify_object(o, f)
    assert o.sensitivity == "financial"
