import json
import sqlite3
import struct
from pathlib import Path

import pytest

from engine import registry,usn_reader
from engine.code_fields import Codebook,update_codes,downstream_dependents,propose_blast_radius
from engine.rename_preview import build,filename


@pytest.fixture
def corpus(tmp_path):
    root=tmp_path/'Canonical Rebuild';root.mkdir()
    (root/'BOOK_01_MORAL.md').write_text('# Moral Law\nHume challenges Moral Law.',encoding='utf-8')
    db=tmp_path/'state/registry.sqlite'
    registry.scan([root],db)
    return root,db


def test_codes_lifecycle_and_separate_publication(corpus):
    root,db=corpus
    book=Codebook()
    for values in [{'concepts':['MADEUP']},{'series':'MADEUP'},{'opposition':'HU'},{'status_level':'canon'},{'confidence':1.1}]:
        with pytest.raises(ValueError):update_codes(db,'W000001',values,codebook=book)
    for level in ['CD','ES','RT']:
        with pytest.raises(ValueError,match='Pipeline'):update_codes(db,'W000001',{'status_level':level})
    update_codes(db,'W000001',{'series':'CR','concepts':['MO','L1'],'opposition':'xHU','status_level':'AP','published':'yes','confidence':.7,'next_review_due':'2026-12-01'})
    with sqlite3.connect(db) as con:
        row=con.execute('SELECT status_level,published,concepts FROM works').fetchone()
    assert row==('AP',1,'["MO", "L1"]')
    update_codes(db,'W000001',{'status_level':'ES'},authority='David')
    with pytest.raises(ValueError,match='human-ruled'):update_codes(db,'W000001',{'status_level':'AP'})
    registry.scan([root],db)
    with sqlite3.connect(db) as con:assert con.execute('SELECT status_level FROM works').fetchone()[0]=='ES'


def test_blast_radius_reverses_dependencies_and_handles_cycles(corpus):
    root,db=corpus
    edges=[{'from_id':'B','to_id':'A','rel_type':'dependsOn'},{'from_id':'C','to_id':'B','rel_type':'dependsOn'},
           {'from_id':'A','to_id':'C','rel_type':'dependsOn'}]
    assert downstream_dependents(edges)['A']==['B','C']
    proposal=[{'from_id':'W000002','to_id':'W000001','rel_type':'dependsOn'}]
    propose_blast_radius(db,proposal)
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT blast_radius FROM works').fetchone()[0] is None
        assert con.execute("SELECT count(*) FROM review_queue WHERE kind='blast_radius'").fetchone()[0]==1


def test_dry_run_names_density_and_misspellings(corpus,tmp_path):
    root,db=corpus
    small=root/'theopyhiscs_picture';small.mkdir()
    (small/'photo.png').write_bytes(b'picture')
    (small/'FIS.html').write_text('notes',encoding='utf-8')
    empty=root/'notes_only';empty.mkdir();(empty/'.fisnote').write_text('note',encoding='utf-8')
    registry.scan([root],db)
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result=build(db,root,tmp_path/'preview')
    assert str(small) in result['misspellings']
    assert any(r['folder']==str(small) and r['real_items']==1 and 'flatten' in r['proposal'] for r in result['density'])
    assert any(r['folder']==str(empty) and r['real_items']==0 for r in result['density'])
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert 'theopyhiscs' in (tmp_path/'preview/REVIEW.md').read_text(encoding='utf-8')
    name=filename('Moral norms','.md','MIM','09',['MO','LW'],'xHU',Codebook())
    assert name=='MIM-09_moral_norms_MO-LW_xHU.md'
    assert not any('_'+level in name for level in ['IN','WK','AP','CD','ES','RT'])


def binary_record(name,reason,usn,frn=12,parent=4):
    encoded=name.encode('utf-16-le');length=60+len(encoded)
    return struct.pack('<IHHQQqqIIIIHH',length,2,0,frn,parent,usn,133000000000000000,reason,0,0,0,len(encoded),60)+encoded


def test_usn_parse_moves_and_split_checkpoint_pairing():
    data=struct.pack('<q',300)+binary_record('old.md',0x1000,100,parent=4)+binary_record('new.md',0x2000,200,parent=5)
    cursor,rows=usn_reader.parse_buffer(data)
    events,pending=usn_reader.events(rows)
    assert cursor==300 and events[0]['event']=='move' and events[0]['old_name']=='old.md' and not pending
    _,pending=usn_reader.events(rows[:1])
    events,pending=usn_reader.events(rows[1:],pending)
    assert events[0]['event']=='move' and not pending
    raw=struct.pack('<q',400)+binary_record('born.txt',0x100,300)+binary_record('gone.txt',0x200,350)
    _,rows=usn_reader.parse_buffer(raw)
    assert [e['event'] for e in usn_reader.events(rows)[0]]==['create','delete']


def test_usn_checkpoint_gaps_and_malformed_records():
    journal={'journal_id':1,'first_usn':100,'next_usn':1000}
    for checkpoint in [{'volume':'C:','journal_id':2,'next_usn':200},{'volume':'C:','journal_id':1,'next_usn':0}]:
        with pytest.raises(ValueError):usn_reader.validate_checkpoint(checkpoint,journal,'C:')
    with pytest.raises(ValueError):usn_reader.parse_buffer(b'bad')
    record=bytearray(binary_record('a.md',0x100,100));struct.pack_into('<H',record,4,3)
    with pytest.raises(ValueError,match='Unsupported'):usn_reader.parse_buffer(struct.pack('<q',200)+record)
