import tempfile
from pathlib import Path

from fis.model import Atlas, FolderRecord, ObjectRecord
from fis import anomaly, rulings


def _atlas():
    folders = {"T1": FolderRecord(object_id="T1", name="PUBLICATION_GOLD",
                                  full_path="C:/c/PUBLICATION_GOLD", node_type="research_territory"),
               "T2": FolderRecord(object_id="T2", name="UNIFICATION_GOLD",
                                  full_path="C:/c/UNIFICATION_GOLD", node_type="research_territory")}
    objs = {f"O{i}": ObjectRecord(object_id=f"O{i}", name=nm, ext="", full_path=f"C:/c/{nm}",
                                  is_dir=False, parent="C:/c", content_type="markdown")
            for i, nm in enumerate(["SOURCE_OF_TRUTH.md", "CANONICAL_all.md"])}
    return Atlas(root="C:/c", objects=objs, folders=folders, clusters=[])


def test_ruling_becomes_policy_and_suppresses_reask():
    a = _atlas()
    anomalies, questions = anomaly.detect(a)
    auth = next(x for x in anomalies if x.family == "authority")
    q = next(qq for qq in questions if qq.anomaly_id == auth.anomaly_id)

    tmp = Path(tempfile.mkdtemp()) / "rulings.jsonl"
    store = rulings.RulingStore(tmp)
    ruling, policy = rulings.make_ruling(q, auth, chosen_index=2,      # "GOLD = outputs, not sources"
                                         scope="corpus",
                                         applies_to_pattern="GOLD|CANONICAL|SOURCE_OF_TRUTH")
    store.record(ruling, policy)

    # re-run: the authority anomaly should now be resolved, not re-asked
    store2 = rulings.RulingStore(tmp)          # reload from disk (append-only persistence)
    anomalies2, _ = anomaly.detect(a)
    names = lambda an: [o.name for o in a.objects.values()] + [f.name for f in a.folders.values()]
    survivors, resolved = store2.apply(anomalies2, names)
    assert not any(x.family == "authority" for x in survivors)
    assert resolved and resolved[0]["family"] == "authority"


def test_policy_predicts_future_item():
    tmp = Path(tempfile.mkdtemp()) / "rulings.jsonl"
    store = rulings.RulingStore(tmp)
    a = _atlas()
    anomalies, questions = anomaly.detect(a)
    auth = next(x for x in anomalies if x.family == "authority")
    q = next(qq for qq in questions if qq.anomaly_id == auth.anomaly_id)
    ruling, policy = rulings.make_ruling(q, auth, 2, "corpus", "GOLD")
    store.record(ruling, policy)
    # a brand-new folder named ..._GOLD gets the learned verdict without asking
    assert store.predict("NEW_THEORY_GOLD") == [q.options[2]]
    assert store.predict("random_folder") == []
