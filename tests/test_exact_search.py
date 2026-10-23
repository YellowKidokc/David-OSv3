import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hub.api.routes_search import router
from hub.api.security import ApiTokenMiddleware
from hub.services.exact_search import search, ROOT

@pytest.fixture
def corpus(tmp_path, monkeypatch):
    cfg=json.loads((ROOT/'config/search.json').read_text())
    cfg.update(roots={'fixture':str(tmp_path)},default_roots=['fixture'])
    config=tmp_path/'settings.json'
    config.write_text(json.dumps(cfg))
    monkeypatch.setenv('DAVIDOS_SEARCH_CONFIG',str(config))
    (tmp_path/'sample.md').write_text('First line\nGod cannot lie\nGod cannot lie again\n',encoding='utf-8')
    return tmp_path

def test_real_literal_and_provenance(corpus):
    result=search('God cannot lie',file_types=['md'])
    assert result['complete']
    assert len(result['results'])==2
    assert result['results'][0]['line']==2
    assert result['results'][0]['canonical_status']=='unknown'
    assert search('God.*lie',file_types=['md'])['results']==[]
    assert len(search('God.*lie',file_types=['md'],regex=True)['results'])==2

def test_limit_and_no_matches(corpus):
    assert search('God',file_types=['md'],maximum_results=1)['incomplete_reason']=='result_limit'
    result=search('missing_phrase',file_types=['md'])
    assert result['complete'] and result['results']==[]

def test_root_and_extension_controls(corpus):
    with pytest.raises(ValueError): search('God',roots=[str(corpus)])
    with pytest.raises(ValueError): search('God',file_types=['md --pre evil'])

def test_invalid_regex_reports_failure(corpus):
    result=search('[',file_types=['md'],regex=True)
    assert not result['complete']
    assert result['incomplete_reason']=='search_error'

def test_api_auth_and_validation(corpus,monkeypatch):
    app=FastAPI();app.include_router(router);app.add_middleware(ApiTokenMiddleware)
    monkeypatch.setenv('FIHUB_API_TOKEN','fixture-secret')
    with TestClient(app) as client:
        assert client.post('/search/exact',json={'query':'God'}).status_code==401
        h={'Authorization':'Bearer fixture-secret'}
        assert client.post('/search/exact',headers=h,json={'query':'God','roots':['bad']}).status_code==400
        response=client.post('/search/exact',headers=h,json={'query':'God','file_types':['md']})
        assert response.status_code==200 and response.json()['returned']==2

def test_pdf_docx_zip_sqlite(corpus):
    import sqlite3, zipfile
    from reportlab.pdfgen import canvas
    from docx import Document
    phrase='ExactFixtureNeedle'
    pdf=canvas.Canvas(str(corpus/'paper.pdf'));pdf.drawString(60,700,phrase);pdf.save()
    doc=Document();doc.add_paragraph(phrase);doc.save(corpus/'paper.docx')
    with zipfile.ZipFile(corpus/'bundle.zip','w') as archive:
        archive.writestr('inside.md',phrase)
    with sqlite3.connect(corpus/'records.db') as db:
        db.execute('create table notes(body text)');db.execute('insert into notes values (?)',(phrase,))
    for ext in ['pdf','docx','zip','db']:
        result=search(phrase,file_types=[ext])
        assert result['complete'], result
        assert result['results'], (ext,result)
        assert phrase in result['results'][0]['passage']
