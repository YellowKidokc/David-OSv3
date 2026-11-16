import uuid

import pytest

from shared.identity.layers import (build_envelope, derive_uuid,
                                    make_dual_relation, short_uuid,
                                    validate_envelope)


def test_short_and_derivative_are_stable():
    root = "4d59aecf-8b21-4f12-9c34-8a12e34c5678"
    assert short_uuid(root) == "u-4D59AECF8B21"
    assert derive_uuid(root, "api", "deep:run-1") == derive_uuid(root, "api", "deep:run-1")


def test_envelope_is_extensible_and_valid():
    envelope = build_envelope(root_uuid="4d59aecf-8b21-4f12-9c34-8a12e34c5678", human_id="MEQU.03.TRUTH")
    envelope["identifiers"].append({
        "order": 20, "scheme": "legacy", "value": "OLD-3",
        "authority": "migration_receipt", "status": "historical",
    })
    assert validate_envelope(envelope) == []


def test_identifier_contract_is_enforced():
    envelope = build_envelope(root_uuid="4d59aecf-8b21-4f12-9c34-8a12e34c5678")
    envelope["identifiers"].append({"order": 20, "scheme": "legacy", "value": "OLD-3"})
    assert validate_envelope(envelope) == ["identifier 0 missing authority, status"]


def test_isomorphism_requires_witness():
    left, right = str(uuid.uuid4()), str(uuid.uuid4())
    with pytest.raises(ValueError, match="mapping-witness"):
        make_dual_relation(left, "ISOMORPHIC_TO", right)
    relation = make_dual_relation(left, "ISOMORPHIC_TO", right,
                                  evidence=[{"mapping": "f", "inverse": "g"}])
    assert relation["dual_id"].startswith("DUAL--")


def test_envelope_cannot_mint_a_document_root():
    with pytest.raises(ValueError, match="registry"):
        build_envelope()
