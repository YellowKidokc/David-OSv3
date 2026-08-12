import os
import tempfile
from pathlib import Path

from fis.atlas import build_atlas
from fis.store import Store
from fis.node_agent import NodeAgent


def _sample_folder():
    d = Path(tempfile.mkdtemp())
    (d / "notes.md").write_text("The master equation governs the chi field. We derive the Lagrangian.")
    (d / "IMG_001.png").write_bytes(b"\x89PNG\r\n")
    (d / "weird.dat").write_bytes(b"\x00\x01\x02")
    sub = d / "proj"; sub.mkdir()
    (sub / "main.py").write_text("print('hi')")
    (sub / ".git").write_text("")
    return d


def test_store_persists_and_searches():
    d = _sample_folder()
    atlas = build_atlas(str(d))
    db = Path(tempfile.mkdtemp()) / "atlas.db"
    st = Store(db)
    stats = st.save_atlas(atlas)
    assert stats["objects_written"] >= 3
    # scanning the DB, not the disk
    hits = st.search("notes")
    assert any("notes.md" in h["name"] for h in hits)
    assert st.counts()["objects"] >= 3
    st.close()


def test_store_mtime_skips_unchanged_on_rescan():
    d = _sample_folder()
    db = Path(tempfile.mkdtemp()) / "atlas.db"
    st = Store(db)
    st.save_atlas(build_atlas(str(d)))
    stats2 = st.save_atlas(build_atlas(str(d)))   # nothing changed
    assert stats2["objects_unchanged"] >= 3        # re-scan is cheap
    st.close()


def test_node_agent_wakes_and_recognizes():
    d = _sample_folder()
    r = NodeAgent(str(d)).wake()
    assert r.n_files == 3
    assert "theophysics" in "".join(r.purpose).lower() or r.folder_class in ("research", "mixed", "media")
    assert "weird.dat" in r.needs_help          # can't understand it -> escalate


def test_node_agent_ping_refuses_forbidden_and_proposes_allowed():
    d = _sample_folder()
    # the program subfolder is red -> delete refused
    prog = NodeAgent(str(d / "proj"))
    prog.wake()
    refused = prog.ping("delete", ["main.py"])
    assert refused["status"] == "refused"
    # a plain rename proposal on the top folder is proposed, never executed
    top = NodeAgent(str(d))
    top.wake()
    res = top.ping("rename", ["IMG_001.png"])
    assert res["status"] in ("proposed", "refused")
    assert res["status"] != "executed"          # nothing ever mutates
