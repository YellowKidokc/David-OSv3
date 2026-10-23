import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hub.api.routes_search import router
from hub.api.security import ApiTokenMiddleware
from hub.services import exact_search

def test_search_launcher_does_not_enable_other_hub_actions(monkeypatch):
    monkeypatch.setenv('FIHUB_SEARCH_ONLY', '1')
    monkeypatch.setenv('FIHUB_API_TOKEN', 'test-key')
    app=FastAPI();app.add_middleware(ApiTokenMiddleware)
    with TestClient(app) as client:
        assert client.get('/docs',headers={'Authorization':'Bearer test-key'}).status_code==403

def test_saved_location_requires_auth_and_preserves_files(tmp_path, monkeypatch):
    monkeypatch.setattr(exact_search, 'ROOT', tmp_path)
    monkeypatch.setenv('FIHUB_API_TOKEN', 'test-key')
    app=FastAPI();app.include_router(router);app.add_middleware(ApiTokenMiddleware)
    source=tmp_path/'papers';source.mkdir();(source/'note.md').write_text('preserved')
    with TestClient(app) as client:
        assert client.post('/search/locations', json={'path':str(source)}).status_code==401
        response=client.post('/search/locations', headers={'Authorization':'Bearer test-key'}, json={'path':str(source)})
        assert response.status_code==200
        alias=response.json()['alias']
        assert json.loads((tmp_path/'.data/search-locations.json').read_text())[alias]==str(source.resolve())
        assert (source/'note.md').read_text()=='preserved'
        assert client.post('/search/locations',headers={'Authorization':'Bearer test-key'},json={'path':'relative'}).status_code==400

def test_hidden_files_are_explicit(tmp_path,monkeypatch):
    cfg=exact_search.load_config()
    cfg.update(roots={'fixture':str(tmp_path)},default_roots=['fixture'])
    config=tmp_path/'settings.json';config.write_text(json.dumps(cfg))
    monkeypatch.setenv('DAVIDOS_SEARCH_CONFIG',str(config))
    hidden=tmp_path/'.hidden';hidden.mkdir();(hidden/'note.md').write_text('HiddenNeedle723')
    assert not exact_search.search('HiddenNeedle723',file_types=['md'])['results']
    assert exact_search.search('HiddenNeedle723',file_types=['md'],include_hidden=True)['results']
