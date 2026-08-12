import pytest

from fis import registry, statement, history


def _reg():
    return registry.load()


# ---- statements (readable, reversible) ----
def test_statement_encode_parse_roundtrip():
    s = statement.Statement(schema="2", batch="B442", root_set="RS04", object_set="OS91",
                            destination="Q1", workflow="W7", policy="02", decision="D14", result="03")
    text = s.encode()
    assert text == "S:2:B442:RS04/OS91>Q1:W7:P2:D14:V3" or text.startswith("S:2:B442:RS04/OS91>Q1")
    back = statement.parse(text)
    assert back.batch == "B442" and back.object_set == "OS91" and back.destination == "Q1"


def test_statement_decompresses_via_registry():
    r = _reg()
    text = "S:2:B442:RS04/OS91>Q1:W7:P2:D14:V3"
    english = statement.decompress(r, text)
    assert "GTQ search roots" in english and "result completed_and_verified" in english


# ---- history capsule (tamper-evident, not reversible) ----
def test_capsule_is_24_chars_and_chains():
    r = _reg()
    cap = history.next_capsule("", r.registry_hash(), b"event-1", [])
    assert cap.short.startswith("H:") and len(cap.short) == 26   # "H:" + 24
    assert history.verify(cap, r.registry_hash(), b"event-1", [])


def test_capsule_detects_tampering():
    r = _reg()
    cap = history.next_capsule("", r.registry_hash(), b"event-1", [])
    assert not history.verify(cap, r.registry_hash(), b"event-TAMPERED", [])


def test_capsule_binds_to_registry_version():
    r = _reg()
    cap = history.next_capsule("", r.registry_hash(), b"e", [])
    assert not history.verify(cap, "deadbeef" * 8, b"e", [])      # different registry -> fails


# ---- registry chain + invariants ----
def test_registry_hash_is_deterministic():
    r1, r2 = _reg(), _reg()
    assert r1.registry_hash() == r2.registry_hash()


def test_seal_then_verify_chain():
    r = _reg()
    r.seal()
    assert r.verify_chain()
    r.data["operations"]["Z"] = "sneaky_edit"        # mutate after sealing
    assert not r.verify_chain()                       # chain now broken


def test_root_set_requires_manifest_hash():
    r = _reg()
    rs = r.root_set("RS04")
    assert rs["count"] == 4 and rs["manifest_hash"]
    r.data["root_sets"]["RS04"]["manifest_hash"] = None
    with pytest.raises(registry.RegistryError):
        r.root_set("RS04")


def test_never_reuse_a_code():
    r = _reg()
    with pytest.raises(registry.RegistryError):
        r.add_code("roots", "02", "SOME/OTHER/PATH")


def test_decisions_are_immutable_citations():
    r = _reg()
    # cannot overwrite; must supersede with a new id
    r.supersede_decision("D14", "D21", {"pdf": "authoritative"}, reason="signed releases")
    assert r.decision("D21")["supersedes"] == "D14"
    assert r.decision("D14")["ruling"]["editable_source"] == ".md"   # original untouched


def test_require_verified_blocks_on_broken_chain():
    r = _reg()
    r.seal()
    r.data["policies"]["01"] = "changed"
    with pytest.raises(registry.RegistryIntegrityError):
        r.require_verified()
