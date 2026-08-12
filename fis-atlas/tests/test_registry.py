import pytest

from fis import registry


def _reg():
    return registry.load()


def test_lookups_resolve_codes():
    r = _reg()
    assert r.lookup("operations", "M") == "move"
    assert r.lookup("roots", "02") == "D:/Old Research"
    assert r.lookup("policies", "03") == "move_after_approval"


def test_capsule_roundtrips_and_verifies_integrity():
    r = _reg()
    cap = r.encode_capsule(node="K7M4", manifest="A9X0", operation="M", source="02",
                           destination="05", policy="03", period="T7", result="03")
    assert len(cap) == 24
    d = r.decode_capsule(cap)
    assert d["operation"] == "M" and d["source"] == "2" and d["result"] == "03"


def test_tampered_capsule_fails_checksum():
    r = _reg()
    cap = r.encode_capsule(node="K7M4", manifest="A9X0", operation="M", source="02",
                           destination="05", policy="03", period="T7", result="03")
    tampered = cap[:10] + "C" + cap[11:]        # flip the operation
    with pytest.raises(registry.RegistryError):
        r.decode_capsule(tampered)


def test_decompress_is_plain_english():
    r = _reg()
    cap = r.encode_capsule(node="K7M4", manifest="A9X0", operation="M", source="02",
                           destination="05", policy="03", period="T7", result="03")
    text = r.decompress(cap)
    assert "move" in text and "D:/Old Research" in text and "move_after_approval" in text


def test_never_reuse_a_code():
    r = _reg()
    with pytest.raises(registry.RegistryError):
        r.add_code("roots", "02", "SOME/OTHER/PATH")     # 02 already means D:/Old Research


def test_superseded_code_is_rejected():
    r = _reg()
    r.supersede("03", "11")
    with pytest.raises(registry.RegistryError):
        r.lookup("policies", "03")


def test_manifest_hash_is_stable(tmp_path):
    r = _reg()
    m = tmp_path / "G7K4.fism"
    m.write_text("obj1\nobj2\n")
    assert r.hash_manifest(m) == r.hash_manifest(m)      # deterministic


def test_folder_capsule_is_decompressible():
    r = _reg()
    cap = registry.folder_capsule(r, "O-abc123def456", risk="red")
    assert len(cap) == 24
    assert "scan" in r.decompress(cap) and "protected" in r.decompress(cap)
