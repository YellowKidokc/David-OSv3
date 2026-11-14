"""Reference implementation of Identity Layers Standard v1.0 (stdlib only)."""
from __future__ import annotations

import re
import uuid
from typing import Any

RELATIONS = {
    "SIMILAR_TO", "STRUCTURALLY_ANALOGOUS_TO", "SYMBOLIC_OF", "REPRESENTS",
    "DERIVED_FROM", "VERSION_OF", "FORMAT_OF", "SAME_WORK_AS",
    "EXACT_CONTENT_AS", "ISOMORPHIC_TO",
}
SHORT_RE = re.compile(r"^u-[0-9A-F]{12,32}$")


def normalize_uuid(value: str | uuid.UUID) -> str:
    return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))


def short_uuid(root_uuid: str | uuid.UUID, length: int = 12) -> str:
    if length < 12 or length > 32:
        raise ValueError("short UUID length must be 12..32 hex characters")
    return "u-" + uuid.UUID(normalize_uuid(root_uuid)).hex[:length].upper()


def derive_uuid(root_uuid: str | uuid.UUID, category: str, key: str) -> str:
    if not category.strip() or not key.strip():
        raise ValueError("category and key are required")
    return str(uuid.uuid5(uuid.UUID(normalize_uuid(root_uuid)), f"{category.strip()}:{key.strip()}"))


def build_envelope(root_uuid: str | uuid.UUID | None = None,
                   human_id: str | None = None) -> dict[str, Any]:
    root = normalize_uuid(root_uuid or uuid.uuid4())
    identifiers = []
    if human_id:
        identifiers.append({"order": 10, "scheme": "human_canonical_id", "value": human_id,
                            "expanded_value": None, "authority": "official_registry",
                            "status": "assigned", "aliases": [], "valid_from": None, "valid_to": None})
    return {"schema_version": "identity-envelope.v1", "root_uuid": root,
            "short_uuid": short_uuid(root), "human_id": human_id,
            "identifiers": identifiers, "relations": [], "derivatives": [], "assessments": []}


def make_dual_relation(left_root_uuid: str, relation_type: str, right_root_uuid: str,
                       evidence: list[dict[str, Any]] | None = None,
                       confidence: float | None = None, status: str = "PROPOSED") -> dict[str, Any]:
    relation = relation_type.upper().strip()
    if relation not in RELATIONS:
        raise ValueError(f"unregistered DUAL relation: {relation_type}")
    left, right = normalize_uuid(left_root_uuid), normalize_uuid(right_root_uuid)
    if relation == "ISOMORPHIC_TO" and not evidence:
        raise ValueError("ISOMORPHIC_TO requires mapping-witness evidence")
    return {"dual_id": f"DUAL--{short_uuid(left)}--{relation}--{short_uuid(right)}",
            "left_root_uuid": left, "relation_type": relation, "right_root_uuid": right,
            "directionality": "directed" if relation in {"REPRESENTS", "DERIVED_FROM", "VERSION_OF", "FORMAT_OF", "SYMBOLIC_OF"} else "symmetric",
            "mapping_or_witness": evidence or [], "confidence": confidence,
            "status": status, "ruled_by": None, "ruled_at": None}


def validate_envelope(envelope: dict[str, Any]) -> list[str]:
    errors = []
    try:
        root = normalize_uuid(envelope.get("root_uuid", ""))
    except (ValueError, AttributeError):
        return ["invalid root_uuid"]
    short = envelope.get("short_uuid", "")
    if not SHORT_RE.match(short):
        errors.append("invalid short_uuid")
    elif not uuid.UUID(root).hex.upper().startswith(short[2:]):
        errors.append("short_uuid is not derived from root_uuid")
    identifiers = envelope.get("identifiers", [])
    if not isinstance(identifiers, list):
        return errors + ["identifiers must be a list"]
    orders = [entry.get("order") for entry in identifiers]
    if len(orders) != len(set(orders)):
        errors.append("identifier order values must be unique")
    required_identifier_fields = {"order", "scheme", "value", "authority", "status"}
    for index, entry in enumerate(identifiers):
        if not isinstance(entry, dict):
            errors.append(f"identifier {index} must be an object")
            continue
        missing = required_identifier_fields - entry.keys()
        if missing:
            errors.append(f"identifier {index} missing {', '.join(sorted(missing))}")
    for relation in envelope.get("relations", []):
        if relation.get("relation_type") not in RELATIONS:
            errors.append(f"unregistered relation {relation.get('relation_type')!r}")
    for key in ("relations", "derivatives", "assessments"):
        if not isinstance(envelope.get(key), list):
            errors.append(f"{key} must be a list")
    return errors
