import sqlite3
from pathlib import Path
from engine.tagger_v3 import legacy_arguments


def test_legacy_catalog_is_preserved_and_options_forward(tmp_path):
    db = tmp_path/'legacy.db'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE files(path TEXT PRIMARY KEY, md5 TEXT)')
        con.execute("INSERT INTO files VALUES('old.md','legacy-hash')")
    before = db.read_bytes()
    args = legacy_arguments([str(tmp_path), '--db', str(db), '--quickhash', '--sidecar', '--force'])
    assert args[:2] == ['scan','--catalog']
    assert args[args.index('--db')+1] == str(tmp_path/'legacy.tagger3.db')
    assert '--write-sidecars' in args and '--force' in args
    assert '--full-hash' not in args
    assert db.read_bytes() == before


def test_legacy_marker_renderer_uses_registry_uuid_and_blocks_remint(tmp_path):
    import runpy
    from uuid import UUID
    import pytest
    file = Path(__file__).resolve().parents[1]/'Theophysics_Tagger/tools/ext_filetagger/legacy_folder_markers.py'
    render = runpy.run_path(str(file))['marker_body']
    text = render(tmp_path, tmp_path)
    token = next(line.split(': ',1)[1] for line in text.splitlines() if line.startswith('folder_id: '))
    assert UUID(token).version == 7
    assert token in render(tmp_path,tmp_path)
    with pytest.raises(ValueError, match='immutable'):
        render(tmp_path,tmp_path,force_new_id=True)


def test_legacy_watch_preserves_explicit_roots_and_exclusions(tmp_path, monkeypatch):
    import json,sys
    from types import SimpleNamespace
    from engine.tagger_v3 import watch_legacy_config
    fake=SimpleNamespace(SKIP_DIRS=set(),SKIP_NAMES=set(),main=lambda args:args)
    monkeypatch.setitem(sys.modules,'tagger3',fake)
    settings=tmp_path/'watch.json'
    settings.write_text(json.dumps({'watch_folders':[str(tmp_path/'a'),str(tmp_path/'b')],
        'db_path':str(tmp_path/'catalog.sqlite'),'skip_dirs':['private'],'skip_names':['secret.txt']}))
    args=watch_legacy_config(settings)
    assert args[0]=='watch' and args.count('--source')==2
    assert 'private' in fake.SKIP_DIRS and 'secret.txt' in fake.SKIP_NAMES


def test_old_marker_id_is_an_alias_with_a_registry_reference(tmp_path):
    import runpy,os
    from shared.identity.registry import IdentityRegistry
    file=Path(__file__).resolve().parents[1]/'Theophysics_Tagger/tools/ext_filetagger/legacy_folder_markers.py'
    (tmp_path/'.folder.fmeta').write_text('folder_id: OLD-FOLDER\n')
    text=runpy.run_path(str(file))['marker_body'](tmp_path,tmp_path)
    registry=IdentityRegistry(os.environ['DAVID_OS_REGISTRY'])
    reference=registry.reference(tmp_path)
    assert 'folder_id: OLD-FOLDER' in text and f"registry_uuid: {reference['uuid7']}" in text
    assert registry.lookup('OLD-FOLDER',scheme='legacy-folder-id')==reference
