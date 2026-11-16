"""Paths remain usable after relocating a clone; guards work on any drive."""
from pathlib import Path
import pytest
from shared.runtime_config import path_setting
from fis import gate
from engine.gate import _is_system


def test_config_paths_resolve_against_config_file_and_environment_wins(tmp_path, monkeypatch):
    folder = tmp_path / 'configuration with spaces'
    folder.mkdir()
    config = folder / 'config.yaml'
    config.write_text('paths:\n  state_dir: local state\n')
    monkeypatch.setenv('DAVID_OS_CONFIG', str(config))
    monkeypatch.delenv('DAVID_OS_STATE_DIR', raising=False)
    monkeypatch.chdir(tmp_path.parent)
    assert path_setting('DAVID_OS_STATE_DIR', 'state_dir', 'unused') == folder / 'local state'
    override = tmp_path / 'override'
    monkeypatch.setenv('DAVID_OS_STATE_DIR', str(override))
    assert path_setting('DAVID_OS_STATE_DIR', 'state_dir', 'unused') == override


def test_credentials_are_rejected_in_config(tmp_path, monkeypatch):
    config = tmp_path / 'config.yaml'
    config.write_text('provider:\n  api_key: forbidden-test-placeholder\n')
    monkeypatch.setenv('DAVID_OS_CONFIG', str(config))
    monkeypatch.delenv('PORTABILITY_TEST_PATH', raising=False)
    with pytest.raises(ValueError, match='environment variables only'):
        path_setting('PORTABILITY_TEST_PATH', 'state_dir', tmp_path)


@pytest.mark.parametrize('path', ['X:/Windows/System32/a', 'E:/Program Files/app/a', '/etc/passwd', '/usr/bin/a'])
def test_system_roots_stay_protected_on_any_drive(path):
    assert _is_system(path)
    assert gate.unsafe(path, gate.defaults()) == 'system root'


@pytest.mark.parametrize('path', ['X:/WindowsNotes/a', '/binary/a', '/tmp/usr-notes/a'])
def test_similar_folder_names_are_not_system_roots(path):
    assert not _is_system(path)


def test_provider_keys_can_only_come_from_environment(monkeypatch):
    from hub.services.provider_router import _to_provider, _from_provider
    monkeypatch.setenv('PORTABILITY_TEST_PROVIDER_KEY', 'test-placeholder')
    provider = _to_provider({'id': 'test', 'key_env': 'PORTABILITY_TEST_PROVIDER_KEY'})
    assert provider.resolved_key == 'test-placeholder'
    assert 'key' not in _from_provider(provider)
    with pytest.raises(ValueError, match='environment variable'):
        _to_provider({'id': 'test', 'key': 'forbidden-test-placeholder'})
