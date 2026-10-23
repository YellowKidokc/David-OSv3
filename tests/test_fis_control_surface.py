from pathlib import Path

from gui.fis_control_surface import applyable_action_keys, build_preview, resolve_scope


def test_selected_scope_rejects_paths_outside_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    inside = root / "inside.md"
    inside.write_text("x", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    assert resolve_scope(root, "selected", [inside, outside]) == [inside.resolve()]


def test_proposal_actions_never_cross_apply_gate(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    preview = build_preview(root, "all", [], ["scan", "tag", "name", "canon"])
    assert applyable_action_keys(preview) == {"scan", "tag"}
    assert preview["source_mutation"] is False


# Drive Harvester extends the existing FIS review/export surface.
def _harvester():
    import pytest
    pytest.importorskip("PySide6")
    from gui import drive_harvester
    return drive_harvester


def test_harvester_search_fields_do_not_leak(tmp_path):
    h = _harvester()
    document = tmp_path / "neutral.md"
    document.write_text("---\ntags: [axiom]\n---\n# Neutral\nDefinition: something else", encoding="utf-8")
    Path(str(document) + ".sidecar.json").write_text('{"topic":"axiom"}', encoding="utf-8")
    profile = h.profile_for("axiom", [])
    for field in ("sidecar", "tags"):
        profile["fields"] = [field]
        assert h.score_file(document, profile)
    for field in ("filename", "heading"):
        profile["fields"] = [field]
        assert h.score_file(document, profile) is None
    document.write_text("# Theorem 1: unrelated\nDefinition: other material", encoding="utf-8")
    profile["fields"] = ["body"]
    assert h.score_file(document, profile) is None


def test_harvester_export_preserves_sources_and_handles_collisions(tmp_path):
    h = _harvester()
    root = tmp_path / "source"
    root.mkdir()
    rows = []
    for folder in ("a", "b"):
        sub = root / folder
        sub.mkdir()
        doc = sub / "axiom.md"
        doc.write_text(folder + " axiom", encoding="utf-8")
        row = h.bare_row(doc)
        row["scan_root"] = str(root)
        rows.append(row)
    profile = h.profile_for("axiom", [])
    for mode in ("flat", "tree", "extension"):
        dest = tmp_path / mode
        dest.mkdir()
        (dest / "axiom.md").write_text("already here", encoding="utf-8")
        manifest = h.export_files(rows, profile, dest, mode)
        assert len({m["exported_as"] for m in manifest}) == 2
        for item in manifest:
            assert item["exported_as"]
            assert (dest / item["exported_as"]).read_bytes() == Path(item["original_path"]).read_bytes()
            assert h.sha256(str(dest / item["exported_as"])) == item["sha256"]
        assert (dest / "axiom.md").read_text() == "already here"
    assert (root / "a" / "axiom.md").read_text() == "a axiom"


def test_harvester_cancelled_export_records_every_unprocessed_file(tmp_path):
    h = _harvester()
    doc = tmp_path / "axiom.md"
    doc.write_text("axiom", encoding="utf-8")
    result = h.export_files([h.bare_row(doc)], h.profile_for("axiom", []),
                            tmp_path / "export", stop=lambda: True)
    assert result[0]["error"] == "Export cancelled"
    assert not (tmp_path / "export" / "axiom.md").exists()
    assert doc.read_text() == "axiom"


def test_duplicate_review_reuses_inventory_and_hashes_only_same_sizes(tmp_path, monkeypatch):
    from engine.symptoms import content
    a, b, c = (tmp_path / name for name in ("a.txt", "b.txt", "c.txt"))
    a.write_text("same"); b.write_text("same"); c.write_text("different-size")
    calls = []
    original = content.digest
    def counted(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(content, "digest", counted)
    monkeypatch.setattr(content, "walk", lambda _: (_ for _ in ()).throw(AssertionError("walk repeated")))
    findings = content.detect_duplicates(tmp_path, files=[a, b, c])
    assert len(findings) == 1
    assert set(calls) == {a, b}
    assert content.detect_duplicates(tmp_path, files=[a, b], stop=lambda: True) == []
