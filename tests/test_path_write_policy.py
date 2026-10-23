from pathlib import Path


def test_generated_fisnotes_are_disabled_globally():
    from engine.path_write_policy import fisnote_write_allowed

    assert not fisnote_write_allowed(Path(r"Z:\vault\folder"))
    assert not fisnote_write_allowed(Path(r"C:\vault\folder"))
    assert not fisnote_write_allowed(Path(r"D:\GitHub\David-OSv3"))
    assert not fisnote_write_allowed(Path(r"G:\GitHub\another-repo"))
    assert not fisnote_write_allowed(Path(r"D:\Documents\ordinary-folder"))


def test_z_drive_guard_is_case_insensitive():
    from engine.path_write_policy import require_fisnote_write_allowed
    import pytest

    with pytest.raises(PermissionError, match=r"disabled globally.*z:"):
        require_fisnote_write_allowed(r"z:\anything")
