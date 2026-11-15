from concurrent.futures import ThreadPoolExecutor
import sqlite3
from uuid import UUID

import pytest
from shared.identity.registry import IdentityRegistry, document_id


def test_issue_reopen_and_lookup(tmp_path):
    path = tmp_path / 'registry.sqlite'
    registry = IdentityRegistry(path)
    row = registry.issue('MIM', 0, 'Mephistopheles')
    assert row['registry_id'] == 'MIM.00_Mephistopheles'
    token = UUID(row['uuid7'])
    assert token.version == 7 and token.variant == 'specified in RFC 4122'
    reopened = IdentityRegistry(path)
    assert reopened.issue('MIM', 0, 'Mephistopheles') == row
    assert reopened.lookup(row['uuid7']) == reopened.lookup(row['registry_id']) == row
    assert reopened.lookup('unknown') is None
    with pytest.raises(ValueError, match='immutable'):
        reopened.issue('MIM', 0, 'Changed-Title')


def test_concurrent_issuance_has_one_winner(tmp_path):
    registry = IdentityRegistry(tmp_path / 'registry.sqlite')
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda _: registry.issue('MIM', 1, 'Original-Title'), range(20)))
    assert len({r['uuid7'] for r in rows}) == 1


@pytest.mark.parametrize('args', [('ab', 1, 'Title'), ('MIM', -1, 'Title'), ('MIM', 100, 'Title'),
    ('MIM', True, 'Title'), ('MIM', 1, ''), ('MIM', 1, '../bad'), ('MIM', 1, 'Title '), ('MIM', 1, 'bad:Name')])
def test_invalid_assignment_is_not_issued(args):
    with pytest.raises(ValueError):
        document_id(*args)


def test_preserves_existing_stage1_tables(tmp_path):
    path = tmp_path / 'registry.sqlite'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE works(work_id TEXT PRIMARY KEY)')
        con.execute("INSERT INTO works VALUES('legacy-work')")
    registry = IdentityRegistry(path)
    registry.issue('MIM', 0, 'Mephistopheles')
    with sqlite3.connect(path) as con:
        assert con.execute('SELECT * FROM works').fetchall() == [('legacy-work',)]


def test_observation_assignment_and_move_preserve_one_uuid(tmp_path):
    r = IdentityRegistry(tmp_path / 'registry.sqlite')
    source = tmp_path / 'draft.md'
    ref = r.reference(source)
    assert ref['registry_id'] is None and UUID(ref['uuid7']).version == 7
    issued = r.assign(source, 'MIM', 0, 'Mephistopheles')
    assert issued['uuid7'] == ref['uuid7']
    destination = tmp_path / 'MIM.00_Mephistopheles.md'
    r.relocate(source, destination)
    assert r.reference(destination) == r.reference(source)
    with pytest.raises(ValueError):
        r.assign(source, 'MIM', 1, 'Other-Title')


def test_registry_does_not_merge_distinct_paths_by_content(tmp_path):
    r = IdentityRegistry(tmp_path / 'registry.sqlite')
    assert r.reference(tmp_path/'a.md')['uuid7'] != r.reference(tmp_path/'b.md')['uuid7']
    with pytest.raises(ValueError):
        r.relocate(tmp_path/'a.md', tmp_path/'b.md')


def test_explicit_migration_is_dry_by_default_and_atomic(tmp_path):
    from shared.identity.migrate import migrate
    path = tmp_path/'registry.sqlite'
    mapping = {'reviewed_by':'David', 'entries':[{'path':str(tmp_path/'a.md'), 'series':'MIM',
        'position':0, 'original_title':'Mephistopheles', 'aliases':[{'scheme':'work','value':'W000001'}]}]}
    assert not migrate(mapping, path)['applied'] and not path.exists()
    first = migrate(mapping, path, True)
    assert migrate(mapping, path, True) == first
    mapping['entries'].append({'path':str(tmp_path/'b.md'), 'series':'MIM', 'position':1,
        'original_title':'Other', 'aliases':[{'scheme':'work','value':'W000001'}]})
    with pytest.raises(ValueError): migrate(mapping, path, True)
    with sqlite3.connect(path) as con:
        assert con.execute('SELECT count(*) FROM document_identities').fetchone()[0] == 1
