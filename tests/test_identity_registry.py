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
