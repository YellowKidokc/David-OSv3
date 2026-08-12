"""Each primitive tested in isolation — proof they stand alone and compose."""
import os
import tempfile
from pathlib import Path

from fis.handlers import lok_search, dec_cut, dec_breakdown, sim_dedupe
from fis.model import ObjectRecord


def _obj(name, path, mtime=1.0):
    size = os.path.getsize(path) if os.path.exists(path) else 10
    return ObjectRecord(object_id="O-" + name, name=name, ext=Path(name).suffix,
                        full_path=path, is_dir=False, parent="", modified=mtime, size=size)


def test_search_is_generic_via_matcher():
    d = Path(tempfile.mkdtemp())
    (d / "a.md").write_text("invoice total due")
    (d / "b.md").write_text("holiday photos")
    matcher = lambda name, text: 1.0 if "invoice" in text else 0.0
    hits = lok_search.search([str(d)], matcher, min_score=0.5)
    assert len(hits) == 1 and hits[0][0].name == "a.md"


def test_cut_flattens_collision_safe():
    objs = [_obj("x.md", "C:/1/x.md"), _obj("x.md", "C:/2/x.md")]
    props = dec_cut.cut(objs, "T")
    tos = [p["to"] for p in props]
    assert tos == ["T/x.md", "T/x_1.md"]          # no collision


def test_breakdown_flattens_tree_and_cleans_folders():
    d = Path(tempfile.mkdtemp()); (d / "sub").mkdir()
    (d / "sub" / "deep.md").write_text("hi")
    props = dec_breakdown.breakdown(str(d))
    assert any(p["action"] == "flatten_move" and p["from"].endswith("deep.md") for p in props)
    assert any(p["action"] == "remove_emptied_folder" for p in props)


def test_dedupe_keeps_newest():
    d = Path(tempfile.mkdtemp())
    (d / "a.md").write_text("same"); (d / "b.md").write_text("same")
    import os
    objs = [_obj("a.md", str(d / "a.md"), mtime=1.0), _obj("b.md", str(d / "b.md"), mtime=9.0)]
    keepers, props = sim_dedupe.dedupe(objs)
    assert len(keepers) == 1 and keepers[0].name == "b.md"    # newest kept
    assert len(props) == 1
