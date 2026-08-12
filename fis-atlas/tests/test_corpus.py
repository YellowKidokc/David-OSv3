from fis.model import Atlas, FolderRecord, ObjectRecord
from fis import corpus


def _mk():
    root = FolderRecord(object_id="R", name="THEOPHYSICS_ORGANIZED",
                        full_path="C:/corpus", rel_path="", depth=0,
                        direct_children=3, total_descendants=5000, total_size=999)
    t1 = FolderRecord(object_id="T1", name="ME_Master_Equation",
                      full_path="C:/corpus/ME_Master_Equation", rel_path="ME_Master_Equation", depth=1)
    t2 = FolderRecord(object_id="T2", name="TEN_LAWS_CANONICAL",
                      full_path="C:/corpus/TEN_LAWS_CANONICAL", rel_path="TEN_LAWS_CANONICAL", depth=1)
    objs = {}
    # numbered docs under T1 + a canonical marker
    for i, nm in enumerate(["00_ARGUMENT_INDEX.md", "01_law.md", "02_law.md", "SOURCE_OF_TRUTH_spine.md"]):
        objs[f"O{i}"] = ObjectRecord(object_id=f"O{i}", name=nm, ext=".md",
                                     full_path=f"C:/corpus/ME_Master_Equation/{nm}", is_dir=False,
                                     parent="C:/corpus/ME_Master_Equation",
                                     rel_path=f"ME_Master_Equation/{nm}", content_type="markdown")
    folders = {"R": root, "T1": t1, "T2": t2}
    return Atlas(root="C:/corpus", objects=objs, folders=folders, clusters=[])


def test_corpus_root_detected():
    a = _mk()
    corpus.apply_corpus_model(a)
    assert a.folders["R"].node_type == "corpus_root"
    assert a.folders["R"].folder_class == "research_corpus"
    assert a.folders["R"].risk == "amber"          # report-only, not red-sealed


def test_territories_inherit_and_get_node_ids():
    a = _mk()
    corpus.apply_corpus_model(a)
    t1 = a.folders["T1"]
    assert t1.node_type == "research_territory"
    assert t1.parent_node == "fis:theophysics-organized"
    assert t1.node_id.startswith("fis:theophysics-organized:")
    assert t1.inherited_policy == "corpus_protected"


def test_permission_tiers_present():
    a = _mk()
    corpus.apply_corpus_model(a)
    perms = a.folders["R"].permissions
    assert "scan" in perms["without_approval"]
    assert "rename" in perms["require_approval"]
    assert "direct_delete" in perms["prohibited"]


def test_numbered_ordering_and_canonical_flags():
    a = _mk()
    corpus.apply_corpus_model(a)
    assert a.folders["T1"].ordering_scheme == "numbered_document_sequence"
    canon = a.folders["R"].canonical_candidates
    assert any("SOURCE_OF_TRUTH" in c for c in canon)
    assert a.folders["R"].open_questions          # surfaced, not auto-trusted
