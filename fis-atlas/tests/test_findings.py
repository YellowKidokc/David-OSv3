from fis.model import Atlas, FolderRecord, ObjectRecord, Cluster
from fis import anomaly, findings


def _corpus_atlas():
    folders = {
        "R": FolderRecord(object_id="R", name="THEO", full_path="C:/c", rel_path="",
                          node_type="corpus_root"),
        "T1": FolderRecord(object_id="T1", name="CANONICAL_CONSOLIDATED_ALL",
                           full_path="C:/c/CANONICAL_CONSOLIDATED_ALL", node_type="research_territory"),
        "T2": FolderRecord(object_id="T2", name="PUBLICATION_GOLD",
                           full_path="C:/c/PUBLICATION_GOLD", node_type="research_territory", risk="red"),
    }
    objs = {}
    for i, nm in enumerate(["SOURCE_OF_TRUTH_spine.md", "paper_FINAL.md", "paper.md",
                            "paper.html", "notes.md", "notes.xlsx"]):
        objs[f"O{i}"] = ObjectRecord(object_id=f"O{i}", name=nm, ext="", full_path=f"C:/c/{nm}",
                                     is_dir=False, parent="C:/c",
                                     content_type="markdown" if nm.endswith(".md")
                                     else "code" if nm.endswith(".html")
                                     else "spreadsheet" if nm.endswith(".xlsx") else "unknown")
    return Atlas(root="C:/c", objects=objs, folders=folders, clusters=[])


def test_authority_anomaly_is_detected_and_blocks():
    a = _corpus_atlas()
    anomalies, questions = anomaly.detect(a)
    auth = [x for x in anomalies if x.family == "authority"]
    assert auth, "should detect competing canonical authority"
    q = [q for q in questions if q.anomaly_id == auth[0].anomaly_id][0]
    assert q.blocking and q.ruling_scope == "corpus"
    assert "rename" in q.affected_actions


def test_show_me_examples_option_present():
    a = _corpus_atlas()
    _, questions = anomaly.detect(a)
    assert any("show me" in o.lower() for q in questions for o in q.options)


def test_priority_orders_bigger_blast_first():
    a = _corpus_atlas()
    _, questions = anomaly.detect(a)
    prios = [q.priority for q in questions]
    assert prios == sorted(prios, reverse=True)


def test_findings_all_have_evidence():
    a = _corpus_atlas()
    anomalies, questions = anomaly.detect(a)
    finds = findings.compile_findings(a, anomalies)
    assert finds
    model = findings.build_report_model(a, finds, questions)
    for f in model["findings"]:
        assert f["evidence_ids"], f"finding {f['finding_id']} has no evidence"
        assert "_warning" not in f


def test_five_part_grammar_present():
    a = _corpus_atlas()
    anomalies, _ = anomaly.detect(a)
    f = findings.compile_findings(a, anomalies)[0]
    for part in ("claim", "evidence_ids", "interpretation", "consequence", "recommended_action"):
        assert getattr(f, part) or part == "evidence_ids"
