"""Keep registry observations made by integration tests out of live state."""
import pytest


@pytest.fixture(autouse=True)
def isolated_identity_registry(tmp_path, monkeypatch):
    monkeypatch.setenv('DAVID_OS_REGISTRY', str(tmp_path / 'identity' / 'registry.sqlite'))
