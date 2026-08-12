import tempfile
from pathlib import Path

import pytest

from fis.lineage import Lineage


def _lin():
    return Lineage(Path(tempfile.mkdtemp()) / "lineage.db")


def test_move_keeps_identity_changes_only_address():
    lin = _lin()
    oid = lin.register(kind="spreadsheet", ext="xlsx",
                       path="H:/Research/MDA/decline_master.xlsx", project="PROJECT-MDA")
    lin.move(oid, "Z:/Archive/America/decline_master.xlsx")
    row = lin.conn.execute("SELECT current_path FROM objects WHERE object_id=?", (oid,)).fetchone()
    assert row["current_path"].startswith("Z:/Archive")     # address changed
    # same object id, and still a member of MDA
    assert oid in {m["object_id"] for m in lin.members("PROJECT-MDA")}
    lin.close()


def test_copy_creates_new_object_descended_from_parent():
    lin = _lin()
    src = lin.register(kind="spreadsheet", ext="xlsx", path="H:/a.xlsx")
    cp = lin.copy(src, "Z:/a_backup.xlsx")
    assert cp != src
    edge = lin.conn.execute("SELECT relationship,tier FROM lineage WHERE parent=? AND child=?",
                            (src, cp)).fetchone()
    assert edge["relationship"] == "copied_from" and edge["tier"] == "recorded"
    lin.close()


def test_convert_split_combine_relationships():
    lin = _lin()
    src = lin.register(kind="doc", ext="md", path="H:/paper.md")
    html = lin.convert(src, "H:/paper.html", "html")
    assert lin.conn.execute("SELECT relationship FROM lineage WHERE child=?", (html,)).fetchone()[0] == "converted_from"
    parts = lin.split(src, ["H:/p1.md", "H:/p2.md"])
    assert len(parts) == 2
    merged = lin.combine([parts[0], parts[1]], "H:/whole.md")
    parents = {r["parent"] for r in lin.conn.execute("SELECT parent FROM lineage WHERE child=?", (merged,))}
    assert parents == set(parts)                            # two parents
    lin.close()


def test_project_membership_survives_relocation():
    lin = _lin()
    a = lin.register(kind="spreadsheet", ext="xlsx", path="H:/MDA/one.xlsx", project="PROJECT-MDA")
    b = lin.register(kind="spreadsheet", ext="xlsx", path="D:/other/two.xlsx")
    lin.add_to_project("PROJECT-MDA", "Moral Decline", [b])
    lin.move(b, "Z:/wherever/two.xlsx")
    members = {m["object_id"] for m in lin.members("PROJECT-MDA")}
    assert members == {a, b}                                # membership independent of location
    lin.close()


def test_trace_follows_the_graph_from_a_clue():
    lin = _lin()
    root = lin.register(kind="spreadsheet", ext="xlsx", path="H:/MDA/decline_master.xlsx",
                        project="PROJECT-MDA")
    cleaned = lin.copy(root, "H:/MDA/decline_clean.xlsx")
    archived = lin.copy(cleaned, "Z:/Archive/decline_v7.xlsx")
    g = lin.trace("MDA", depth=3)
    ids = {n["object_id"] for n in g["nodes"]}
    assert {root, cleaned, archived} <= ids                # traced roots -> descendants
    assert all(e["tier"] in ("recorded", "verified", "inferred", "possible") for e in g["edges"])
    lin.close()


def test_reconstructed_relationship_is_not_recorded():
    lin = _lin()
    a = lin.register(kind="doc", ext="md", path="H:/x.md")
    b = lin.register(kind="doc", ext="md", path="H:/y.md")
    lin.relate(a, b, "version_of", tier="inferred")
    edge = lin.conn.execute("SELECT tier FROM lineage WHERE parent=? AND child=?", (a, b)).fetchone()
    assert edge["tier"] == "inferred"                       # never presented as recorded fact
    with pytest.raises(AssertionError):
        lin.relate(a, b, "version_of", tier="recorded")     # cannot fake a recorded edge
    lin.close()
