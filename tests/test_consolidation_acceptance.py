"""Disposable end-to-end check; companion GUI checkout is optional in unit CI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

import pytest
from fis import service, transaction, approval
from fis.index import Store
from shared.identity.registry import IdentityRegistry


def test_inventory_identity_tagger_prediction_gui_apply_rollback(tmp_path, monkeypatch):
    gui = Path(os.environ.get('PREDICTION_GUI_ROOT', ''))
    if not (gui/'API/server.py').is_file():
        pytest.skip('set PREDICTION_GUI_ROOT to the companion cleanup checkout')
    repo = Path(__file__).resolve().parents[1]
    source = tmp_path/'source'; source.mkdir()
    document = source/'draft notes.md'
    original = b'# Grace\nA method using evidence and information.\n'
    document.write_bytes(original)
    registry = IdentityRegistry(os.environ['DAVID_OS_REGISTRY'])
    issued = registry.assign(document, 'MIM', 0, 'Mephistopheles')
    tagged_db = tmp_path/'tagger.sqlite'
    subprocess.run([sys.executable, str(repo/'Theophysics_Tagger/tools/tagger3.py'), 'scan',
        '--source',str(source),'--db',str(tagged_db),'--output',str(tmp_path/'exports'),
        '--tagged',str(tmp_path/'tagged'),'--workers','1','--catalog'], check=True, capture_output=True, text=True)
    import sqlite3
    with sqlite3.connect(tagged_db) as con:
        assert con.execute('SELECT registry_uuid FROM registry_refs WHERE path=?',(str(document),)).fetchone()[0] == issued['uuid7']
    assert document.read_bytes() == original
    store = Store(tmp_path/'fis-state'); service.configure_root(store, source)
    plan = service.make_plan(store, source, html=False)
    assert plan['rows'] and plan['rows'][0]['file']['registry_uuid'] == issued['uuid7']
    assert plan['rows'][0]['preference']['auto_approval'] is False
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(repo),str(gui)])
    env['PREDICTION_LEDGER'] = str(tmp_path/'gui.sqlite')
    code = 'from API.server import Handler,ThreadingHTTPServer; s=ThreadingHTTPServer(("127.0.0.1",0),Handler); print(s.server_port,flush=True); s.serve_forever()'
    process = subprocess.Popen([sys.executable,'-u','-c',code], cwd=gui, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = process.stdout.readline().strip()
        assert port.isdigit(), process.stderr.read() if process.poll() is not None else 'GUI failed to start'
        endpoint = 'http://127.0.0.1:'+port
        rows = [r['id'] for r in plan['rows'] if not r['flag']]
        receipt = approval.record_decision(plan, rows, 'approved', endpoint=endpoint)
        # GUI ledger is reopened/read independently: it recorded the exact choice.
        with sqlite3.connect(env['PREDICTION_LEDGER']) as con:
            assert con.execute('SELECT decision,actor FROM notification_decisions').fetchall() == [('approved','David')]
        restarted = Store(tmp_path/'fis-state')
        token = approval.authorize(restarted, receipt)
        run = transaction.apply(restarted, plan['id'], token)
        assert run['status'] == 'applied'
        target = Path(plan['rows'][0]['target'])
        assert target.read_bytes() == original
        assert registry.reference(target)['uuid7'] == issued['uuid7']
        with pytest.raises(PermissionError): approval.authorize(restarted, receipt)
        assert transaction.undo(Store(tmp_path/'fis-state'), run['id'])['conflicts'] == []
        assert document.read_bytes() == original and not target.exists()
    finally:
        process.terminate()
        try: process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill(); process.communicate()
