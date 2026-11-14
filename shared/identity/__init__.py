"""Canonical document identity and extensible identity-layer helpers."""

from .identity import parse_artifact_ref, parse_document_id
from .layers import (build_envelope, derive_uuid, make_dual_relation,
                     normalize_uuid, short_uuid, validate_envelope)

__all__ = ["build_envelope", "derive_uuid", "make_dual_relation",
           "normalize_uuid", "parse_artifact_ref", "parse_document_id",
           "short_uuid", "validate_envelope"]
