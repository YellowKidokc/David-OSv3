import json
import pytest
from hub.config.folder_profiles import FolderProfile, FolderProfileRegistry

def test_extended_fields_roundtrip(tmp_path):
    cfg = {"profiles": [{
        "path": str(tmp_path), "folder_role": "obsidian_vault",
        "allowed_actions": ["scan", "tag", "rename"],
        "blocked_actions": ["delete", "move"],
        "irrelevant_actions": ["dedupe"],
        "sidecar_writer": "obsidian", "report_type": "vault",
        "approval_floor": "approval_required"}]}
    p = tmp_path / "folder_profiles.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    reg = FolderProfileRegistry.load(p)
    prof = reg.match(tmp_path / "note.md")
    assert prof.folder_role == "obsidian_vault"
    assert "delete" in prof.blocked_actions
    assert prof.approval_floor == "approval_required"

def test_unknown_key_still_rejected():
    from hub.config.folder_profiles import validate_folder_profile_config, FolderProfileConfigError
    with pytest.raises(FolderProfileConfigError):
        validate_folder_profile_config({"profiles": [{"path": "x", "bogus_key": 1}]})

def test_windows_case_insensitive_prefix_match(tmp_path):
    cfg = {"profiles": [{"path": str(tmp_path).upper(), "folder_role": "shallow"}]}
    p = tmp_path / "fp.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    reg = FolderProfileRegistry.load(p)
    prof = reg.match(str(tmp_path).lower() + "\\sub\\file.txt")
    assert prof.folder_role == "shallow"
