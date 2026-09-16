#!/usr/bin/env python3
"""NSE-1.0 enclosure: one envelope, profile-specific payloads.

L0 source bytes stay canonical. Semantic payloads are derived and may change.
The Master Equation manifest uses payload_profile=formal_system. That profile
is not the universal lossless format for conversations or living projects.
"""
from __future__ import annotations

from typing import Any

NSE_FORMAT = "NSE-1.0"
PAYLOAD_PROFILES = (
    "document",
    "conversation",
    "project_state",
    "formal_system",
    "executable_system",
    "corpus",
)


def infer_profile(text: str, relative_path: str) -> str:
    low = text.lower()
    name = relative_path.lower()
    if "master_equation" in name or "n = master_equation_chi" in low or "gate_01" in low and "c != chi" in low:
        return "formal_system"
    if name.endswith((".py", ".js", ".ts", ".lean")):
        return "executable_system"
    if "payload_profile: conversation" in low or name.endswith(".jsonl"):
        return "conversation"
    return "document"


def enclosure(
    *,
    object_id: str,
    source_sha256: str,
    relative_path: str,
    created_utc: str,
    payload_profile: str,
    payload: dict[str, Any],
    extraction_version: str,
) -> dict[str, Any]:
    if payload_profile not in PAYLOAD_PROFILES:
        payload_profile = "document"
    return {
        "semantic_enclosure": {
            "format": NSE_FORMAT,
            "object_id": object_id,
            "object_type": payload_profile,
            "source_hash": source_sha256,
            "source_authority": "original_bytes",
            "created_at": created_utc,
            "provenance": {
                "source_files": [relative_path],
                "extraction_version": extraction_version,
                "model": "",
                "prompt_version": "",
            },
            "reconstruction_contract": {
                "original_preserved": True,
                "semantic_layer_is_interpretive": True,
                "unsupported_inferences_forbidden": True,
            },
            "payload_profile": payload_profile,
            "payload": payload,
        }
    }


def document_payload(compact: dict[str, Any], extraction: dict[str, Any] | None) -> dict[str, Any]:
    headings = compact.get("headings") or []
    claims = compact.get("claims") or []
    equations = compact.get("equations") or []
    return {
        "identity": {
            "title": headings[0] if headings else compact.get("filename"),
            "document_type": compact.get("profile"),
            "purpose": "derived compact index; L0 remains authoritative",
        },
        "structure": {
            "sections": headings,
            "equations": equations,
        },
        "content": {
            "claims": claims,
            "central_thesis": claims[0] if claims else (headings[1] if len(headings) > 1 else ""),
        },
        "boundaries": {
            "supported": "only what L0 encodes",
            "unsupported": "inferences not evidenced in L0",
        },
        "reconstruction": {
            "minimal_summary": compact.get("minimal"),
            "seed_material": compact,
            "l1_statistics": (extraction or {}).get("statistics"),
        },
    }


def formal_system_payload(compact: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        **document_payload(compact, None),
        "specialization": "canonical_formal_object",
        "parent_profile": "project_state",
        "gates_present": "C != chi" in text and "S_eff" in text,
        "lean_boundary_present": "LEAN_NOT_ALLOWED" in text or "Lean" in text,
        "routing": compact.get("minimal"),
    }
