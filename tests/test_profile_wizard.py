import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "01_PROFILE"))
import profile_core as pc  # noqa: E402

def test_evidence_detects_obsidian_vault(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "note.md").write_text("# hi", encoding="utf-8")
    ev = pc.scan_evidence(tmp_path)
    assert ev["has_obsidian"] is True
    sugg = pc.suggest_answers(pc.load_questionnaire(REPO / "config/rules/onboarding_questions.v1.json"), ev)
    assert sugg["primary_domains"]["value"]  # something suggested, not blank

def test_evidence_detects_code_project(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
    ev = pc.scan_evidence(tmp_path)
    assert ev["has_project_markers"] is True

def test_scan_is_bounded_so_the_wizard_never_hangs(tmp_path):
    # a deep, wide tree must come back fast and say it bailed
    d = tmp_path
    for i in range(8):
        d = d / f"d{i}"
        d.mkdir()
        for j in range(20):
            (d / f"f{j}.md").write_text("x", encoding="utf-8")
    ev = pc.scan_evidence(tmp_path)
    assert ev["file_count"] <= 5000
    assert "scan_truncated" in ev

def test_build_profile_maps_answers():
    q = {"core_questions": [], "evidence_based_followups": [],
         "default_profile_template": {"file_profile": {"default_safety": {"execution_mode": "preview_only"}}}}
    prof = pc.build_profile(Path("D:/x"), {"environment_type": "research",
                                           "automation_comfort": "approval_required"}, q)
    assert prof["folder_role"] == "research"
    assert prof["approval_floor"] == "approval_required"

def test_build_profile_comfort_choices_from_questionnaire():
    # real questionnaire choices, not invented tokens
    assert pc.build_profile(Path("D:/x"), {"automation_comfort": "allow_safe_rules"}, {})["approval_floor"] == "auto_after_threshold"
    assert pc.build_profile(Path("D:/x"), {"automation_comfort": "report_only"}, {})["approval_floor"] == "preview_only"
    assert pc.build_profile(Path("D:/x"), {"automation_comfort": "suggest_actions"}, {})["approval_floor"] == "suggest_only"

def test_do_not_touch_none_blocks_nothing():
    prof = pc.build_profile(Path("D:/x"), {"do_not_touch": "none"}, {})
    assert "blocked_actions" not in prof

def test_do_not_touch_paths_kept_as_hints_not_blanket_block():
    prof = pc.build_profile(Path("D:/x"), {"do_not_touch": "C:/Windows, *.env"}, {})
    assert "blocked_actions" not in prof
    assert prof["routing_hints"]["do_not_touch"] == ["C:/Windows", "*.env"]

def test_write_profile_creates_entry_and_marker(tmp_path):
    profiles = tmp_path / "folder_profiles.json"
    target = tmp_path / "vault"; target.mkdir()
    pc.write_profile(target, {"path": str(target), "folder_role": "obsidian_vault",
                              "allowed_actions": ["scan", "tag"], "blocked_actions": ["delete"]},
                     profiles, answers={"environment_type": "personal"}, evidence={"has_obsidian": True})
    saved = json.loads(profiles.read_text(encoding="utf-8"))
    assert saved["profiles"][0]["folder_role"] == "obsidian_vault"
    marker = json.loads((target / ".folder.fmeta").read_text(encoding="utf-8"))
    assert marker["schema"] == "fis.folder_profile/1.0"
    assert marker["answers"]["environment_type"] == "personal"

def test_never_writes_inside_protected_marker(tmp_path):
    protected = tmp_path / "proj"; protected.mkdir()
    (protected / ".git").mkdir()
    profiles = tmp_path / "folder_profiles.json"
    pc.write_profile(protected, {"path": str(protected), "folder_role": "code"},
                     profiles, answers={}, evidence={})
    assert profiles.exists()                     # registry entry fine
    assert not (protected / ".folder.fmeta").exists()  # marker skipped in project roots

def test_partial_answers_write_nothing(tmp_path):
    # build_profile and suggest_answers are pure; only write_profile touches disk.
    profiles = tmp_path / "folder_profiles.json"
    pc.build_profile(tmp_path, {"environment_type": "mixed"}, {"core_questions": []})
    assert not profiles.exists()

def test_write_profile_dedupes_case_insensitively(tmp_path):
    profiles = tmp_path / "folder_profiles.json"
    target = tmp_path / "vault"; target.mkdir()
    pc.write_profile(target, {"path": str(target), "folder_role": "research"}, profiles, {}, {})
    pc.write_profile(target, {"path": str(target).upper(), "folder_role": "research"}, profiles, {}, {})
    saved = json.loads(profiles.read_text(encoding="utf-8"))
    assert len(saved["profiles"]) == 1  # same folder, one entry, on a case-insensitive OS

def test_write_profile_refuses_corrupt_registry(tmp_path):
    import pytest
    profiles = tmp_path / "folder_profiles.json"
    profiles.write_text("{truncated", encoding="utf-8")
    target = tmp_path / "vault"; target.mkdir()
    with pytest.raises(ValueError, match="corrupt"):
        pc.write_profile(target, {"path": str(target)}, profiles, {}, {})
