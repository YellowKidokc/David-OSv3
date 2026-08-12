"""The dumb, stable core: walk objects, classify, cluster, evaluate rules,
attach handlers on demand. Preview-only — never mutates source files.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import scan, classify, cluster, corpus, understand, symptoms, rules as rules_mod
from .handlers import registry
from .model import Atlas


def build_atlas(root: str, rules_path: str | None = None, max_objects: int = 20000) -> Atlas:
    objects, folders = scan.scan_tree(root, max_objects=max_objects)

    # index children per folder for folder classification
    children_by_folder: dict[str, list] = {}
    names_by_folder: dict[str, list] = {}
    for o in objects.values():
        children_by_folder.setdefault(o.parent, []).append(o)
    for f in folders.values():
        # direct child folder names
        names = [g.name for g in folders.values()
                 if g.full_path != f.full_path
                 and str(Path(g.full_path).parent) == f.full_path]
        names += [c.name for c in children_by_folder.get(f.full_path, [])]
        names_by_folder[f.full_path] = names

    for f in folders.values():
        classify.classify_folder(f, names_by_folder.get(f.full_path, []),
                                 children_by_folder.get(f.full_path, []))

    folder_by_path = {f.full_path: f for f in folders.values()}
    for o in objects.values():
        folder = folder_by_path.get(o.parent)
        if folder is None:
            from .model import FolderRecord
            folder = FolderRecord(object_id="", name="", full_path=o.parent)
        classify.classify_object(o, folder)

    clusters = cluster.build_clusters(objects, folders)

    atlas_tmp = Atlas(root=str(Path(root).resolve()), objects=objects, folders=folders, clusters=clusters)
    corpus.apply_corpus_model(atlas_tmp)   # node ids, tiers, corpus_root vs territory

    # comprehension (und) + symptom orchestration (every folder passes through)
    comp = understand.get_comprehender()
    for f in folders.values():
        kids = children_by_folder.get(f.full_path, [])
        profile = understand.comprehend_folder(comp, kids)
        f.domains, f.topics = profile.domains, profile.topics
        if profile.domains:
            f.purpose = understand.purpose_sentence(f.folder_class, profile, len(kids))
            f.evidence.add(f"comprehension: {', '.join(profile.domains[:2])}"
                           + (f" · {', '.join(profile.signals[:2])}" if profile.signals else ""))
        f.symptoms = [h.to_dict() for h in symptoms.run_symptoms(f, kids)]

    # rules (data-driven)
    rpath = rules_path or (Path(__file__).parent.parent / "rules" / "default.rules")
    rules = rules_mod.load_rules(rpath)
    rules_mod.apply_rules(objects, rules)

    # attach dec/normalize handler for anything proposed to rename
    normalize = registry.get("dec/normalize_name")
    for o in objects.values():
        if o.proposed_treatment == "rename" and normalize:
            proposed = normalize(o.name)
            if proposed != o.name:
                o.evidence.add(f"proposed name: {proposed}")
                o.relationships.append(f"rename_to:{proposed}")

    atlas = Atlas(root=str(Path(root).resolve()), objects=objects, folders=folders,
                  clusters=clusters, generated_at=datetime.now(timezone.utc).isoformat())
    return atlas


def build_report(atlas: Atlas, rulings_path: str | None = None) -> dict:
    """Anomaly detection -> apply learned policies -> finding compiler -> report_model."""
    from . import anomaly, findings, rulings as rul
    anomalies, _ = anomaly.detect(atlas)

    # apply learned policies: already-ruled anomalies stop re-asking (the memory loop)
    resolved = []
    rpath = rulings_path or (Path("_atlas_out") / "rulings.jsonl")
    store = rul.RulingStore(rpath)

    def names_for(a):
        ids = set(a.evidence_ids)
        out = [o.name for o in atlas.objects.values() if o.object_id in ids]
        out += [f.name for f in atlas.folders.values() if f.object_id in ids]
        return out

    if store.policies:
        anomalies, resolved = store.apply(anomalies, names_for)

    # rebuild questions from surviving anomalies (preserve priority order)
    _, questions = anomaly.detect(atlas)
    live_ids = {a.anomaly_id for a in anomalies}
    questions = [q for q in questions if q.anomaly_id in live_ids]

    finds = findings.compile_findings(atlas, anomalies)
    model = findings.build_report_model(atlas, finds, questions)
    model["resolved_by_policy"] = resolved
    return model
