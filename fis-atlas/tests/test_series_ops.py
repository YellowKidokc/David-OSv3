import tempfile
from pathlib import Path

from fis import series, operations
from fis.model import ObjectRecord


def _obj(name, folder, content):
    d = Path(folder); d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(content)
    return ObjectRecord(object_id="O-" + str(p), name=name, ext=".md",
                        full_path=str(p), is_dir=False, parent=str(d),
                        size=len(content), modified=1.0, content_type="markdown")


def test_ownership_rises_with_corroborating_folders():
    base = tempfile.mkdtemp()
    # SAME file content appears in 5 different GTQ folders -> strong corroboration
    hits = []
    for i in range(5):
        o = _obj("gtq_law01.md", f"{base}/folder{i}", "Genesis to Quantum law 01 identical body")
        hits.append((o, 0.6))
    # a lone weak match in one folder
    hits.append((_obj("maybe.md", f"{base}/other", "quantum only mention"), 0.2))

    members = series.assess(hits)
    top = members[0]
    assert top.n_folders == 5
    assert top.ownership_prob > 0.9          # corroborated across many folders
    assert top.verdict == "member"

    lone = [m for m in members if m.representative_name == "maybe.md"][0]
    assert lone.ownership_prob < 0.35 and lone.verdict == "weak"


def test_signature_set_is_the_recurring_core():
    base = tempfile.mkdtemp()
    hits = []
    for name in ("law01.md", "law02.md"):
        for i in range(4):
            hits.append((_obj(name, f"{base}/f{i}_{name}", f"Genesis to Quantum {name} body"), 0.6))
    members = series.assess(hits)
    sig = series.signature_set(members)
    assert len(sig) == 2                      # both recurring files are the series core


def test_alias_matcher_recognizes_gtq_and_full_name():
    m = series.series_matcher(series.GTQ_ALIASES)
    assert m("x.md", "this is the Genesis to Quantum series") >= 0.5
    assert m("GTQ_notes.md", "") >= 0.5       # alias in the name
    assert m("x.md", "grocery list") == 0.0


def test_operation_carries_warnings_and_follow_ops():
    op = operations.get("sim/dedupe")
    assert op is not None
    assert any("hash before" in w.lower() for w in op.warnings)
    assert any("mirror" in w.lower() for w in op.watch_for)      # intentional mirror caution
    assert op.reads_from == "sqlite_store"                       # scan the DB, not the drive


def test_breakdown_warns_about_lost_context():
    op = operations.get("dec/breakdown")
    assert any("loses folder context" in w.lower() for w in op.warnings)
