import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from folder_hub.service import FolderHub
from folder_hub.web import create_app


@pytest.fixture
def hub(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    (source/'paper.md').write_text('# A paper\nAn actual source.',encoding='utf-8')
    service = FolderHub(tmp_path/'state')
    scope = service.add_hub(source,'Test folder')
    return service,scope,source


def test_changes_and_receipts_without_source_mutation(hub):
    service,scope,source = hub
    before = (source/'paper.md').read_bytes()
    result = service.command('scan',scope['id'])
    assert result['status'] == 'completed'
    assert len(result['result']['changes']['added']) == 1
    assert (source/'paper.md').read_bytes() == before
    assert not (source/'FIS.html').exists()
    assert (service.home/'hubs'/scope['id']/'FIS.html').is_file()
    (source/'paper.md').write_text('# A paper\nChanged content.',encoding='utf-8')
    result = service.command('scan',scope['id'])
    assert result['result']['changes']['changed'] == [str(source/'paper.md')]
    (source/'paper.md').rename(source/'renamed.md')
    result = service.command('scan',scope['id'])
    assert result['result']['changes']['missing'] == [str(source/'paper.md')]
    assert result['result']['changes']['added'] == [str(source/'renamed.md')]
    assert len(list((service.home/'OUTBOX/MANA').glob('*.json'))) == 3


def test_nested_hub_owns_subtree_even_after_parent_baseline(hub):
    service,scope,source = hub
    nested = source/'Desktop'
    nested.mkdir()
    (nested/'inside.txt').write_text('nested',encoding='utf-8')
    service.command('scan',scope['id'])
    assert len(service.records(scope['id'])) == 2
    child = service.add_hub(nested,'Desktop')
    assert len(service.records(scope['id'])) == 1
    service.command('scan',child['id'])
    assert len(service.records(child['id'])) == 1
    with pytest.raises(ValueError,match='specific hub'):
        service.path(scope,'Desktop/inside.txt')
    result = service.command('scan',scope['id'])
    assert result['status'] == 'completed'
    assert not result['result']['changes']['missing']


def test_scanner_skips_secrets_and_generated_pages(hub):
    service,scope,source = hub
    (source/'.env').write_text('secret',encoding='utf-8')
    (source/'FIS.html').write_text('existing generated page',encoding='utf-8')
    (source/'node_modules').mkdir()
    (source/'node_modules'/'dep.js').write_text('dependency',encoding='utf-8')
    service.command('scan',scope['id'])
    assert [Path(f['path']).name for f in service.records(scope['id'])] == ['paper.md']
    assert (source/'FIS.html').read_text(encoding='utf-8') == 'existing generated page'


def test_read_refuses_changed_and_outside_sources(hub):
    service,scope,source = hub
    service.command('scan',scope['id'])
    assert service.read(scope['id'],'paper.md')['text'].startswith('# A paper')
    with pytest.raises(ValueError,match='outside'):
        service.read(scope['id'],'../../outside.txt')
    (source/'paper.md').write_text('edited later',encoding='utf-8')
    with pytest.raises(ValueError,match='changed'):
        service.read(scope['id'],'paper.md')


def test_excerpts_and_model_unconfigured(hub,monkeypatch):
    service,scope,source = hub
    (source/'paper.md').write_text('A'*13000,encoding='utf-8')
    service.command('scan',scope['id'])
    assert service.read(scope['id'],'paper.md')['partial']
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    assert service.ask(scope['id'],'What is here?')['status'] == 'not_configured'


def test_model_receives_only_scoped_selected_sources(hub,monkeypatch):
    service,scope,source = hub
    service.command('scan',scope['id'])
    monkeypatch.setenv('DEEPSEEK_API_KEY','fixture-not-a-key')
    with patch('hub.api.routes_openai_compat._call_deepseek',return_value='A source-based answer') as call:
        answer = service.ask(scope['id'],'Explain this',['paper.md'])
    assert answer['status'] == 'answered'
    messages = call.call_args.args[0]
    assert 'An actual source.' in messages[1].content
    assert 'untrusted' in messages[0].content


def test_scan_limit_rolls_back_instead_of_inferencing_missing(hub):
    service,scope,source = hub
    service.command('scan',scope['id'])
    baseline = service.records(scope['id'])
    config = service.config()
    config['hubs'][0]['max_files'] = 1
    service.save_config(config)
    (source/'new.md').write_text('new',encoding='utf-8')
    result = service.command('scan',scope['id'])
    assert result['status'] == 'failed' and 'limit' in result['error']
    assert service.records(scope['id']) == baseline


def test_state_can_be_excluded_within_drive_scope(tmp_path):
    root = tmp_path/'drive'
    root.mkdir()
    (root/'source.txt').write_text('source',encoding='utf-8')
    service = FolderHub(root/'owned-state')
    scope = service.add_hub(root,'Drive',kind='drive')
    result = service.command('scan',scope['id'])
    assert result['status'] == 'completed'
    assert [Path(f['path']).name for f in service.records(scope['id'])] == ['source.txt']


def test_offline_root_does_not_mark_sources_missing(hub):
    service,scope,source = hub
    service.command('scan',scope['id'])
    baseline = service.records(scope['id'])
    source.rename(source.with_name('offline'))
    result = service.command('scan',scope['id'])
    assert result['status'] == 'failed'
    assert service.records(scope['id']) == baseline


def test_http_session_scope_and_static_ui(hub):
    service,scope,source = hub
    app = create_app(service.home,allowed_hosts=('testserver',))
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert client.get('/static/app.js').status_code == 200
        request = {'action':'scan','hub':scope['id']}
        assert client.post('/api/commands',json=request).status_code == 403
        headers = {'X-FIS-Token':app.state.token,'Origin':'http://testserver'}
        assert client.post('/api/commands',json=request,headers=headers).json()['status'] == 'completed'
        assert client.get('/folder?id='+scope['id']).status_code == 200
        assert client.post('/api/commands',json={'action':'delete','hub':scope['id']},headers=headers).status_code == 400
        assert client.get('/api/state',headers={'Host':'evil.example'}).status_code == 403


def test_child_folder_context_and_pause_are_scoped(hub,monkeypatch):
    service,scope,source = hub
    nested = source/'chapter'
    nested.mkdir()
    (nested/'inside.md').write_text('# Child\nChild source.',encoding='utf-8')
    service.command('scan',scope['id'])
    view = service.view(scope['id'],'chapter')
    assert len(view['files']) == 1
    assert view['files'][0]['path'] == str(nested/'inside.md')
    assert service.view(scope['id'])['children'] == [{'name':'chapter','relative':'chapter'}]
    with pytest.raises(ValueError,match='outside this folder'):
        service.ask(scope['id'],'Question',['paper.md'],'chapter')
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    assert service.ask(scope['id'],'Question',relative='chapter')['context_summary']['files'] == 1
    assert service.command('pause',scope['id'])['status'] == 'completed'
    assert FolderHub(service.home).hub(scope['id'])['enabled'] is False
    assert service.command('scan',scope['id'])['status'] == 'failed'
    assert service.command('resume',scope['id'])['status'] == 'completed'
