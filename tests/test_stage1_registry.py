import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from engine import registry


@pytest.fixture
def corpus(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    return source, tmp_path/'state/registry.sqlite'


def rows(db, table):
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute('SELECT * FROM '+table)]


def test_inventory_duplicates_versions_unreadable_and_noop(corpus):
    source, db = corpus
    (source/'BOOK_01_A.txt').write_text('# A document\nAn argument.', encoding='utf-8')
    (source/'copy.txt').write_bytes((source/'BOOK_01_A.txt').read_bytes())
    (source/'format.md').write_text('# A document\n\nAn   argument.', encoding='utf-8')
    (source/'image.bin').write_bytes(b'\x00\xff')
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    result = registry.scan([source], db)
    assert result['added'] == 4
    assert len(rows(db, 'files')) == 4
    assert len(rows(db, 'versions')) == 2
    assert {'byte_duplicate', 'text_equivalent_version', 'nabla'} <= {r['kind'] for r in rows(db, 'review_queue')}
    assert all(r['status'] == 'unset' and r['address'] is None for r in rows(db, 'nabla'))
    snapshot = {t: rows(db, t) for t in ['files', 'works', 'versions', 'series', 'nabla', 'review_queue']}
    exports = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in db.parent.glob('*.csv')}
    exports['REGISTRY_MASTER.md'] = ((db.parent/'REGISTRY_MASTER.md').read_bytes(), (db.parent/'REGISTRY_MASTER.md').stat().st_mtime_ns)
    with patch.object(registry, 'sha256_file', side_effect=AssertionError('No rehash on unchanged scan')):
        result = registry.scan([source], db)
    assert result['unchanged'] == 4 and result['hashed'] == 0
    assert snapshot == {t: rows(db, t) for t in snapshot}
    for name, (content, mtime) in exports.items():
        assert (db.parent/name).read_bytes() == content
        assert (db.parent/name).stat().st_mtime_ns == mtime
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}


def test_failed_extraction_remains_visible(corpus):
    source, db = corpus
    (source/'bad.md').write_bytes(b'\xff\xfe\x00')
    registry.scan([source], db)
    assert rows(db, 'files')[0]['readable'] == 'failed'
    assert any(r['kind'] == 'extraction_failure' for r in rows(db, 'review_queue'))


def test_revision_preserves_approved_metadata_and_history(corpus):
    source, db = corpus
    paper = source/'BOOK_01_A.md'
    paper.write_text('# Title\nOriginal revision', encoding='utf-8')
    registry.scan([source], db)
    work = rows(db, 'works')[0]
    version = rows(db, 'versions')[0]
    with sqlite3.connect(db) as con:
        con.execute("UPDATE works SET standing='canon', preferred_version_id=? WHERE work_id=?", (version['version_id'], work['work_id']))
        con.execute("UPDATE nabla SET status='approved' WHERE version_id=?", (version['version_id'],))
    paper.write_text('# Title\nChanged and longer revision', encoding='utf-8')
    registry.scan([source], db)
    assert len(rows(db, 'works')) == 1
    assert len(rows(db, 'versions')) == 2
    assert rows(db, 'works')[0]['standing'] == 'canon'
    assert rows(db, 'works')[0]['preferred_version_id'] == version['version_id']
    assert next(r for r in rows(db, 'nabla') if r['version_id'] == version['version_id'])['status'] == 'approved'
    assert rows(db, 'files')[0]['version_id'] != version['version_id']


def test_nabla_proposal_roundtrip_and_approval_protection(corpus):
    source, db = corpus
    (source/'paper.txt').write_text('A paper', encoding='utf-8')
    registry.scan([source], db)
    version = rows(db, 'versions')[0]
    proposal = {'filing': {'domain': 'THEOPHYSICS', 'entity': 'PAPER', 'state': 'W', 'audience': 'AI_RESEARCH', 'use': 'T', 'risk': 'R1'},
                'vector': {v: 3 if v in 'GMSKRFC' else 0 for v in registry.VARIABLES},
                'confidence': {v: .8 for v in registry.VARIABLES}, 'classifier': 'test-fixture/human-supplied',
                'protocol_version': registry.PROTOCOL, 'source_sha256': version['source_sha256']}
    result = registry.propose_nabla(db, version['version_id'], proposal)
    assert registry.atlas().decode(result['address'])['hash_valid']
    assert rows(db, 'nabla')[0]['status'] == 'proposed'
    assert any(r['kind'] == 'nabla_vector' for r in rows(db, 'review_queue'))
    with sqlite3.connect(db) as con:
        con.execute("UPDATE nabla SET status='approved'")
    with pytest.raises(ValueError, match='Approved'):
        registry.propose_nabla(db, version['version_id'], proposal)


def test_audience_validation():
    core = registry.atlas()
    for audience in core.AUDIENCES:
        core.Filing('SCIENCE', 'PAPER', 'W', audience, 'T', 'R0').validate()
    with pytest.raises(ValueError, match='audience'):
        core.Filing('SCIENCE', 'PAPER', 'W', 'anything', 'T', 'R0').validate()


def test_missing_files_and_overlapping_roots(corpus):
    source, db = corpus
    nested = source/'nested'
    nested.mkdir()
    paper = nested/'a.txt'
    paper.write_text('first', encoding='utf-8')
    registry.scan([source, nested], db)
    assert len(rows(db, 'files')) == 1
    paper.unlink()
    registry.scan([source, nested], db)
    assert rows(db, 'files')[0]['present'] == 0
    assert rows(db, 'versions')


def test_source_cannot_contain_output(corpus):
    source, db = corpus
    with pytest.raises(ValueError, match='outside'):
        registry.scan([source], source/'registry.sqlite')
    with pytest.raises(ValueError, match='outside'):
        registry.scan([source], db, output=source)


def test_series_code_collision_and_work_ids_never_reused(tmp_path):
    first, second = tmp_path/'Alpha Beta', tmp_path/'Another Book'
    first.mkdir()
    second.mkdir()
    (first/'BOOK_01_A.txt').write_text('one', encoding='utf-8')
    (second/'BOOK_01_A.txt').write_text('two', encoding='utf-8')
    db = tmp_path/'state/registry.sqlite'
    registry.scan([first, second], db)
    assert len({r['code'] for r in rows(db, 'series')}) == 2
    ids = {r['work_id'] for r in rows(db, 'works')}
    (first/'BOOK_02_B.txt').write_text('three', encoding='utf-8')
    registry.scan([first], db)
    assert ids < {r['work_id'] for r in rows(db, 'works')}


def test_changed_source_during_hash_is_queued(corpus):
    source, db = corpus
    p = source/'paper.txt'
    p.write_text('first', encoding='utf-8')
    original = registry.sha256_file
    def changing_hash(path):
        result = original(path)
        Path(path).write_text('changed during hash', encoding='utf-8')
        return result
    with patch.object(registry, 'sha256_file', side_effect=changing_hash):
        registry.scan([source], db)
    assert rows(db, 'files')[0]['readable'] == 'failed'
    assert rows(db, 'files')[0]['sha256'] is None
    assert any(r['kind'] == 'extraction_failure' for r in rows(db, 'review_queue'))


def test_title_overlap_only_proposes_group_and_does_not_choose_latest(corpus):
    source, db = corpus
    (source/'Shared argument v1.md').write_text('# Shared argument\nEarlier content', encoding='utf-8')
    (source/'Shared argument v2.md').write_text('# Shared argument\nLater content', encoding='utf-8')
    registry.scan([source], db)
    assert len(rows(db, 'works')) == 2
    assert any(r['kind'] == 'work_group' for r in rows(db, 'review_queue'))
    assert all(r['preferred_version_id'] is None for r in rows(db, 'works'))
    assert all(r['supersedes'] is None for r in rows(db, 'versions'))


def test_extraction_requests_complete_text(corpus):
    source, db = corpus
    (source/'paper.pdf').write_bytes(b'fixture')
    with patch.object(registry.text_extractor, 'extract_text', return_value='Extracted document') as extractor:
        registry.scan([source], db)
    extractor.assert_called_once_with(str(source/'paper.pdf'), limit=None)
    assert rows(db, 'files')[0]['readable'] == 'yes'


def test_failed_observation_retries(corpus):
    source, db = corpus
    (source/'paper.pdf').write_bytes(b'fixture')
    with patch.object(registry.text_extractor, 'extract_text', return_value=''):
        registry.scan([source], db)
    with patch.object(registry.text_extractor, 'extract_text', return_value='Recovered text'):
        result = registry.scan([source], db)
    assert result['hashed'] == 1
    assert rows(db, 'files')[0]['readable'] == 'yes'


def test_record_type_ruling_retains_identity_history_and_survives_scan(corpus):
    source, db = corpus
    marker = source/'.fisnote'
    marker.write_text('system marker', encoding='utf-8')
    (source/'00_SERIES_INDEX.md').write_text('# Series index', encoding='utf-8')
    (source/'Untitled.md').write_text('# The First Reading', encoding='utf-8')
    registry.scan([source], db)
    original_files = rows(db, 'files')
    original_versions = rows(db, 'versions')
    original_ids = {w['work_id'] for w in rows(db, 'works')}
    by_name = {Path(f['path']).name: next(v['work_id'] for v in original_versions if v['version_id'] == f['version_id']) for f in original_files}
    for name, kind in [('.fisnote', 'infrastructure'), ('00_SERIES_INDEX.md', 'index')]:
        registry.set_record_type(db, by_name[name], kind, ruled_by='David', reason='Pilot grouping ruling')
    assert {w['work_id'] for w in rows(db, 'works')} == original_ids
    assert rows(db, 'files') == original_files
    assert rows(db, 'versions') == original_versions
    assert all(w['canon_status'] is None and w['standing'] is None for w in rows(db, 'works'))
    assert len([n for n in rows(db, 'nabla') if n['status'] == 'not_applicable']) == 2
    pending = [r for r in rows(db, 'review_queue') if r['status'] == 'pending']
    assert not any(r['kind'] == 'work' and r['subject'] in {by_name['.fisnote'], by_name['00_SERIES_INDEX.md']} for r in pending)
    assert not registry.set_record_type(db, by_name['.fisnote'], 'infrastructure', ruled_by='David', reason='same')['changed']
    snapshot = {t: rows(db, t) for t in ['files', 'works', 'versions', 'nabla', 'review_queue']}
    result = registry.scan([source], db)
    assert result['hashed'] == 0
    assert snapshot == {t: rows(db, t) for t in snapshot}
    master = (db.parent/'REGISTRY_MASTER.md').read_text(encoding='utf-8')
    assert '1 proposed works · 1 infrastructure · 1 index' in master
    assert '## Infrastructure and indexes' in master
    assert next(w for w in rows(db, 'works') if w['work_id'] == by_name['Untitled.md'])['preferred_title'] == 'The First Reading'
    assert (source/'Untitled.md').exists()
    marker.write_text('revised marker', encoding='utf-8')
    registry.scan([source], db)
    assert all(n['status'] == 'not_applicable' for n in rows(db, 'nabla') if n['work_id'] == by_name['.fisnote'])
    registry.set_record_type(db, by_name['.fisnote'], 'work', ruled_by='David', reason='Undo test ruling')
    assert next(w for w in rows(db, 'works') if w['work_id'] == by_name['.fisnote'])['record_type'] == 'work'


def test_record_type_migration_from_prior_schema(tmp_path):
    db = tmp_path/'old.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE works(id INTEGER PRIMARY KEY AUTOINCREMENT, work_id TEXT UNIQUE)')
        con.execute("INSERT INTO works(work_id) VALUES('W000001')")
    with registry.connect(db) as con:
        row = con.execute('SELECT * FROM works').fetchone()
        assert row['work_id'] == 'W000001'
        assert row['record_type'] == 'work'
        assert row['record_type_ruling_json'] is None
