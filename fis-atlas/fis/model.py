"""The atlas record types.

The crucial distinction (spec): four SEPARATE questions per object, never
collapsed into one score —
    what_is_it        identity / content-type / role
    belongs_with      cluster / project / relationships
    certainty         confidence in the classification
    authorized        what we are permitted to do (independent of certainty)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Provenance:
    """Why FIS reached a conclusion — evidence, not vibes."""
    reasons: list[str] = field(default_factory=list)

    def add(self, reason: str) -> None:
        if reason and reason not in self.reasons:
            self.reasons.append(reason)


@dataclass
class ObjectRecord:
    # --- Identity ---
    object_id: str
    name: str
    ext: str
    full_path: str
    is_dir: bool

    # --- Position ---
    parent: str = ""
    depth: int = 0
    rel_path: str = ""

    # --- Physical state ---
    size: int = 0
    created: Optional[float] = None
    modified: Optional[float] = None
    accessed: Optional[float] = None

    # --- What is it? ---
    content_type: str = "unknown"     # markdown|image|archive|code|empty_folder|...
    detected_role: str = "unknown"    # draft|reference|project_file|receipt|export|backup|temp
    sensitivity: str = "unknown"      # personal|business|financial|legal|secret|public
    activity: str = "unknown"         # recently_used|inactive|abandoned|indeterminate

    # --- What does it belong with? ---
    clusters: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)  # duplicate_of:X, sidecar_of:Y, ...
    domains: list[str] = field(default_factory=list)        # comprehension: theophysics, physics, ...

    # --- Risk / permission ---
    risk: str = "green"               # green|amber|red
    red_flags: list[str] = field(default_factory=list)
    authorized_actions: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)

    # --- Proposed treatment ---
    proposed_treatment: str = "review"    # keep|rename|move|archive|protect|quarantine|review
    probable_destination: str = ""
    second_destination: str = ""

    # --- Confidence (two separate numbers) ---
    class_confidence: float = 0.0     # certainty about WHAT it is
    action_confidence: float = 0.0    # certainty about the proposed action

    # --- Evidence ---
    evidence: Provenance = field(default_factory=Provenance)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence"] = self.evidence.reasons
        return d


@dataclass
class FolderRecord:
    object_id: str
    name: str
    full_path: str
    rel_path: str = ""
    depth: int = 0

    direct_children: int = 0
    total_descendants: int = 0
    total_size: int = 0
    empty: bool = False

    type_distribution: dict[str, int] = field(default_factory=dict)
    folder_class: str = "unknown"     # programming|system|office|creative|research|media|data|archive|inbox|mixed
    behaves_like: str = "unknown"     # project|archive|inbox|collection|accidental
    organization_pattern: str = "unknown"

    risk: str = "green"
    red_flags: list[str] = field(default_factory=list)
    move_breaks_relationships: bool = False
    allowed_actions: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)

    # --- node identity + inheritance (corpus spec) ---
    node_id: str = ""
    node_type: str = "folder"          # corpus_root | research_territory | folder
    parent_node: str = ""
    inherited_policy: str = ""         # e.g. corpus_protected

    # --- four permission tiers (corpus spec) ---
    permissions: dict = field(default_factory=dict)   # {without_approval, as_proposals, require_approval, prohibited}

    # --- authority / canon ---
    ordering_scheme: str = ""          # numbered_document_sequence | none
    canonical_candidates: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    class_confidence: float = 0.0
    purpose: str = ""
    domains: list[str] = field(default_factory=list)     # comprehension profile
    topics: list[str] = field(default_factory=list)
    symptoms: list[dict] = field(default_factory=list)   # matched symptom-registry hits
    evidence: Provenance = field(default_factory=Provenance)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence"] = self.evidence.reasons
        return d


@dataclass
class Cluster:
    cluster_id: str
    label: str
    kind: str                          # duplicates|markdown|images|archives|projects|empty|protected|ambiguous|misc
    members: list[str] = field(default_factory=list)   # object_ids
    proposed_rule: str = ""            # "these N -> Screenshots/Unsorted"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Atlas:
    root: str
    objects: dict[str, ObjectRecord] = field(default_factory=dict)
    folders: dict[str, FolderRecord] = field(default_factory=dict)
    clusters: list[Cluster] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "generated_at": self.generated_at,
            "counts": {
                "objects": len(self.objects),
                "folders": len(self.folders),
                "clusters": len(self.clusters),
            },
            "folders": [f.to_dict() for f in self.folders.values()],
            "objects": [o.to_dict() for o in self.objects.values()],
            "clusters": [c.to_dict() for c in self.clusters],
        }
