import sqlite3
from fis.fis_namer import run_auto_approve


def test_legacy_batch_cannot_approve_its_own_predictions(tmp_path):
    db=tmp_path/'legacy.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE files(path,name,ext,mtime,chi_domain,content_type,chi_confidence,chi_json,folder_class,status,classified_at,proposed_name,approved,approval_note)')
        con.execute("INSERT INTO files VALUES('paper.md','paper.md','.md',1700000000,'theology','paper',0.99,'{}','document','active','now',NULL,NULL,NULL)")
    counts=run_auto_approve(str(db))
    assert counts['auto_approved']==0 and counts['queued']==1
    with sqlite3.connect(db) as con:
        proposed,approved,note=con.execute('SELECT proposed_name,approved,approval_note FROM files').fetchone()
    assert proposed and approved is None and 'GUI review required' in note
