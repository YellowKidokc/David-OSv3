"""Stage 1: in-place inventory and proposed work/version registry. No source writes.

python -m engine.registry scan ROOT [ROOT ...]
python -m engine.registry nabla-propose VERSION_ID input.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from engine.fingerprint import sha256_file
from engine import text_extractor

REPO = Path(__file__).resolve().parents[1]
TOOL = 'stage1-registry/1.1'
RULEBOOK = 'TAG_TAXONOMY_v0.4'
PROTOCOL = 'nabla-atlas/0-3-v1'
VARIABLES = 'GMESTKRQFC'
FIREWALL = ('a valid signature proves the ENCODING is consistent, never that the classification is accurate or the claims true; '
            'E scores disorder OF THE ARTIFACT, not its subject (a clear paper about brokenness is E0); '
            'confidence is stored separately and never makes a document disordered; '
            '0/3 stored scores and any 1–3 working ratings are different systems — never mixed, always provenance-tagged.')
PROVENANCE = 'tool_version TEXT NOT NULL, rulebook_version TEXT NOT NULL'


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def key(value):
    return hashlib.sha256(dump(value).encode('utf-8')).hexdigest()


def atlas():
    spec = importlib.util.spec_from_file_location('stage1_nabla_atlas', REPO/'03_CLASSIFY/00_SHARED/nabla/nabla_atlas.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def connect(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript(f'''
    CREATE TABLE IF NOT EXISTS series (
      code TEXT PRIMARY KEY CHECK(length(code) BETWEEN 2 AND 5), identity TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL, aliases_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'proposed', {PROVENANCE});
    CREATE TABLE IF NOT EXISTS works (
      id INTEGER PRIMARY KEY AUTOINCREMENT, work_id TEXT UNIQUE, series_code TEXT REFERENCES series(code),
      paper_number TEXT, display_code TEXT UNIQUE, preferred_title TEXT NOT NULL,
      preferred_version_id TEXT REFERENCES versions(version_id), status TEXT NOT NULL DEFAULT 'proposed',
      standing TEXT, domain TEXT, tags_json TEXT, canon_status TEXT, published INTEGER, verified INTEGER,
      aliases_json TEXT NOT NULL, {PROVENANCE});
    CREATE TABLE IF NOT EXISTS versions (
      version_id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(work_id),
      source_sha256 TEXT, text_sha256 TEXT, supersedes TEXT REFERENCES versions(version_id),
      reason_preferred TEXT, files_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'proposed',
      created_at TEXT NOT NULL, {PROVENANCE});
    CREATE TABLE IF NOT EXISTS files (
      path TEXT PRIMARY KEY, root TEXT NOT NULL, drive TEXT, size INTEGER, mtime_ns INTEGER,
      sha256 TEXT, text_sha256 TEXT, extension TEXT, readable TEXT NOT NULL,
      extraction_error TEXT, extraction_method TEXT, normalization TEXT, observed_title TEXT,
      version_id TEXT REFERENCES versions(version_id), first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
      present INTEGER NOT NULL DEFAULT 1, {PROVENANCE});
    CREATE TABLE IF NOT EXISTS nabla (
      version_id TEXT PRIMARY KEY REFERENCES versions(version_id), work_id TEXT NOT NULL REFERENCES works(work_id),
      domain TEXT, entity TEXT, state TEXT, audience TEXT, use TEXT, risk TEXT,
      {', '.join(v+' INTEGER CHECK('+v+' IN (0,3))' for v in VARIABLES)},
      signature TEXT, address TEXT, filename_safe TEXT, confidence_json TEXT,
      decode_sentence TEXT, record_json TEXT, protocol_version TEXT NOT NULL,
      classifier TEXT, classified_at TEXT, source_sha256 TEXT, source_text_sha256 TEXT,
      status TEXT NOT NULL DEFAULT 'unset', {PROVENANCE});
    CREATE TABLE IF NOT EXISTS review_queue (
      review_id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL, evidence_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, {PROVENANCE});
    CREATE TABLE IF NOT EXISTS change_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, at TEXT NOT NULL,
      action TEXT NOT NULL, subject TEXT NOT NULL, detail_json TEXT NOT NULL, {PROVENANCE});
    CREATE INDEX IF NOT EXISTS registry_bytes ON files(sha256);
    CREATE INDEX IF NOT EXISTS registry_text ON files(text_sha256);
    ''')
    columns = {r['name'] for r in con.execute('PRAGMA table_info(works)')}
    if 'record_type' not in columns:
        con.execute("ALTER TABLE works ADD COLUMN record_type TEXT NOT NULL DEFAULT 'work' CHECK(record_type IN ('work','infrastructure','index'))")
    if 'record_type_ruling_json' not in columns:
        con.execute('ALTER TABLE works ADD COLUMN record_type_ruling_json TEXT')
    code_fields = {'series':'TEXT', 'concepts':"TEXT NOT NULL DEFAULT '[]'", 'opposition':'TEXT',
                   'status_level':'TEXT', 'confidence':'REAL', 'next_review_due':'TEXT',
                   'blast_radius':'TEXT', 'code_fields_provenance_json':'TEXT'}
    for name, definition in code_fields.items():
        if name not in columns:
            con.execute(f'ALTER TABLE works ADD COLUMN {name} {definition}')
    con.commit()
    return con


def log(con, run, action, subject, detail):
    con.execute('INSERT INTO change_log(run_id,at,action,subject,detail_json,tool_version,rulebook_version) VALUES(?,?,?,?,?,?,?)',
                (run, now(), action, subject, dump(detail), TOOL, RULEBOOK))


def queue(con, run, kind, subject, evidence):
    identity = key([kind, subject, evidence])
    result = con.execute('INSERT OR IGNORE INTO review_queue VALUES(?,?,?,?,?,?,?,?)',
                        (identity, kind, subject, dump(evidence), 'pending', now(), TOOL, RULEBOOK))
    if result.rowcount:
        log(con, run, 'review_proposed', subject, {'kind': kind, 'review_id': identity})


def normalize(text):
    # Whitespace-only normalization preserves case, punctuation, and word order.
    return ' '.join(unicodedata.normalize('NFC', text).split())


def extract(path):
    ext = path.suffix.lower()
    if ext in {'.md', '.markdown', '.txt', '.fisnote', '.rst'}:
        try:
            return path.read_text(encoding='utf-8-sig'), 'yes', None, 'complete-utf8'
        except (OSError, UnicodeError) as error:
            return '', 'failed', str(error), 'complete-utf8'
    if ext in {'.pdf', '.docx', '.html', '.htm'}:
        # Explicitly request complete extraction from the existing helper; no
        # sampled/truncated text is ever used as a version identity.
        text = text_extractor.extract_text(str(path), limit=None)
        if text:
            return text, 'yes', None, 'engine.text_extractor/complete'
        return '', 'failed', 'Existing extractor returned no text (empty, unsupported content, missing dependency or read failure)', 'engine.text_extractor'
    return '', 'no', None, 'metadata-only/unsupported-format'


def title_of(path, text):
    heading = re.search(r'^#\s+(.+)$', text, re.M)
    return heading.group(1).strip() if heading else path.stem.replace('_', ' ')


def series_for(con, root, run):
    identity = str(root)
    row = con.execute('SELECT code FROM series WHERE identity=?', (identity,)).fetchone()
    if row:
        return row['code']
    name = root.name
    base = ''.join(word[0] for word in re.findall(r'[A-Za-z]+', name)).upper()[:5]
    base = base if len(base) >= 2 else 'REG'
    code = base
    counter = 0
    while con.execute('SELECT 1 FROM series WHERE code=?', (code,)).fetchone():
        counter += 1
        code = 'S'+key([identity, counter])[:4].upper()
    con.execute('INSERT INTO series VALUES(?,?,?,?,?,?,?)', (code, identity, name, dump([name]), 'proposed', TOOL, RULEBOOK))
    log(con, run, 'series_proposed', code, {'identity': identity, 'name': name})
    queue(con, run, 'series', code, {'root': identity, 'name': name, 'basis': 'root-derived provisional code; human confirmation required'})
    return code


def new_work(con, row, run):
    code = series_for(con, Path(row['root']), run)
    match = re.match(r'(?:BOOK|PAPER|CHAPTER)[ _-]*(\d+[A-Z]?)\b', Path(row['path']).stem.replace('_', ' '), re.I)
    number = match.group(1).upper() if match else None
    display = f'{code}-{number}' if number else None
    if display and con.execute('SELECT 1 FROM works WHERE display_code=?', (display,)).fetchone():
        display = None
    cur = con.execute('''INSERT INTO works(series_code,paper_number,display_code,preferred_title,aliases_json,tool_version,rulebook_version)
                         VALUES(?,?,?,?,?,?,?)''', (code, number, display, row['observed_title'], dump([Path(row['path']).stem]), TOOL, RULEBOOK))
    work_id = f'W{cur.lastrowid:06d}'
    con.execute('UPDATE works SET work_id=? WHERE id=?', (work_id, cur.lastrowid))
    queue(con, run, 'work', work_id, {'path': row['path'], 'title': row['observed_title'], 'status': 'proposed singleton; not a canonical ruling'})
    log(con, run, 'work_added', work_id, {'path': row['path']})
    return work_id


def assign_version(con, row, old, run):
    # Preserve each physical instance. Shared version membership remains proposed.
    match = None
    if row['text_sha256']:
        match = con.execute('SELECT * FROM versions WHERE text_sha256=? AND status=? ORDER BY created_at LIMIT 1',
                            (row['text_sha256'], 'proposed')).fetchone()
    if match is None and row['sha256']:
        match = con.execute('SELECT * FROM versions WHERE source_sha256=? AND status=? ORDER BY created_at LIMIT 1',
                            (row['sha256'], 'proposed')).fetchone()
    if match:
        paths = sorted(set(json.loads(match['files_json'])) | {row['path']})
        if paths != json.loads(match['files_json']):
            con.execute('UPDATE versions SET files_json=? WHERE version_id=?', (dump(paths), match['version_id']))
            log(con, run, 'version_member_proposed', match['version_id'], {'path': row['path']})
        return match['version_id']
    work_id = None
    if old and old['version_id']:
        work_id = con.execute('SELECT work_id FROM versions WHERE version_id=?', (old['version_id'],)).fetchone()['work_id']
    work_id = work_id or new_work(con, row, run)
    record_type = con.execute('SELECT record_type FROM works WHERE work_id=?', (work_id,)).fetchone()[0]
    version_id = 'V'+uuid.uuid4().hex
    con.execute('INSERT INTO versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (version_id, work_id, row['sha256'], row['text_sha256'], None, None, dump([row['path']]), 'proposed', now(), TOOL, RULEBOOK))
    con.execute('''INSERT INTO nabla(version_id,work_id,protocol_version,source_sha256,source_text_sha256,tool_version,rulebook_version,status)
                   VALUES(?,?,?,?,?,?,?,?)''', (version_id, work_id, PROTOCOL, row['sha256'], row['text_sha256'], TOOL, RULEBOOK,
                   'unset' if record_type == 'work' else 'not_applicable'))
    if record_type == 'work':
        queue(con, run, 'version', version_id, {'work_id': work_id, 'path': row['path'],
              'previous_version_candidate': old['version_id'] if old else None, 'basis': 'source observation; supersedes and preferred version unset'})
        queue(con, run, 'nabla', version_id, {'status': 'unset', 'reason': 'No semantic classifier invoked; filing fields, vector and confidence await a provenance-bearing proposal'})
    log(con, run, 'version_added', version_id, {'work_id': work_id, 'path': row['path']})
    return version_id


def proposed_groups(con, run):
    for column, kind in [('sha256', 'byte_duplicate'), ('text_sha256', 'text_equivalent_version')]:
        groups = con.execute(f'SELECT {column},count(*) FROM files WHERE present=1 AND {column} IS NOT NULL GROUP BY {column} HAVING count(*)>1').fetchall()
        for digest, _ in groups:
            paths = [r[0] for r in con.execute(f'SELECT path FROM files WHERE present=1 AND {column}=? ORDER BY path', (digest,))]
            queue(con, run, kind, digest, {'paths': paths, 'basis': column, 'certain_byte_equality': column == 'sha256', 'cleanup_authorized': False})
    # Conservative title candidates only: never merge on fuzzy evidence.
    buckets = {}
    for row in con.execute('SELECT * FROM files WHERE present=1 ORDER BY path'):
        stem = Path(row['path']).stem.lower()
        stem = re.sub(r'\b(?:draft|final|copy|v\d+(?:[._]\d+)*)\b', ' ', stem.replace('_', ' '))
        tokens = tuple(re.findall(r'[a-z0-9]+', stem))
        if len(tokens) >= 2:
            buckets.setdefault((str(Path(row['path']).parent), tokens), []).append(row)
    for (parent, tokens), rows in buckets.items():
        if len({r['version_id'] for r in rows}) > 1:
            queue(con, run, 'work_group', key([parent, tokens]), {'paths': [r['path'] for r in rows],
                  'basis': 'same folder and same title tokens after removing explicit revision markers', 'status': 'proposed only'})


def scan(roots, db_path=REPO/'_data/registry.sqlite', output=None, *, exclude_roots=(), skip=None, max_files=None):
    for raw in roots:
        path = Path(raw).expanduser().absolute()
        if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
            raise ValueError('Source roots must not traverse links or junctions')
    roots = sorted({Path(r).expanduser().resolve(strict=True) for r in roots}, key=str)
    db_path = Path(db_path).resolve()
    output = Path(output or db_path.parent).resolve()
    excluded = [Path(p).resolve() for p in exclude_roots]
    def omitted(path):
        return any(path.resolve().is_relative_to(p) for p in excluded) or bool(skip and skip(path))
    for root in roots:
        if not root.is_dir():
            raise NotADirectoryError(root)
        if ((db_path.is_relative_to(root) and not any(db_path.is_relative_to(p) for p in excluded)) or
            (output.is_relative_to(root) and not any(output.is_relative_to(p) for p in excluded))):
            raise ValueError('Registry and exports must be outside source roots')
    stats = {'added': 0, 'changed': 0, 'unchanged': 0, 'hashed': 0, 'extracted': 0, 'missing': 0, 'errors': 0}
    run = uuid.uuid4().hex
    with connect(db_path) as con:
        seen = set()
        for root in roots:
            walk_errors = []
            for here, dirs, names in os.walk(root, followlinks=False, onerror=walk_errors.append):
                for name in list(dirs):
                    p = Path(here)/name
                    if omitted(p):
                        dirs.remove(name)
                    elif p.is_symlink() or getattr(p, 'is_junction', lambda: False)():
                        dirs.remove(name)
                        walk_errors.append(OSError('Linked directory not traversed: '+str(p)))
                for name in sorted(names):
                    path = Path(here)/name
                    if omitted(path):
                        continue
                    identity = str(path)
                    if identity in seen:
                        continue
                    if max_files is not None and len(seen) >= max_files:
                        raise ValueError(f'Scan limit {max_files} reached; transaction rolled back. Narrow this hub or raise its configured limit.')
                    seen.add(identity)
                    old = con.execute('SELECT * FROM files WHERE path=?', (identity,)).fetchone()
                    try:
                        if path.is_symlink():
                            raise OSError('Linked file not read')
                        st = path.stat()
                        if old and old['present'] and old['readable'] != 'failed' and old['size'] == st.st_size and old['mtime_ns'] == st.st_mtime_ns:
                            stats['unchanged'] += 1
                            continue
                        stats['hashed'] += 1
                        digest = sha256_file(identity)
                        text, readable, error, method = extract(path)
                        stats['extracted'] += int(readable != 'no')
                        after = path.stat()
                        if (st.st_size, st.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise OSError('Source changed during observation; retry required')
                        normalized = normalize(text)
                        text_hash = hashlib.sha256(normalized.encode()).hexdigest() if normalized else None
                        row = dict(path=identity, root=str(root), drive=path.drive, size=st.st_size, mtime_ns=st.st_mtime_ns,
                                   sha256=digest, text_sha256=text_hash, extension=path.suffix.lower(), readable=readable,
                                   extraction_error=error, extraction_method=method, normalization='NFC-whitespace-v1',
                                   observed_title=title_of(path, text))
                    except (OSError, UnicodeError) as error:
                        row = dict(path=identity, root=str(root), drive=path.drive, size=None, mtime_ns=None,
                                   sha256=None, text_sha256=None, extension=path.suffix.lower(), readable='failed',
                                   extraction_error=str(error), extraction_method='failed', normalization='NFC-whitespace-v1', observed_title=path.stem)
                    row['version_id'] = assign_version(con, row, old, run) if not old or old['sha256'] != row['sha256'] or old['text_sha256'] != row['text_sha256'] else old['version_id']
                    row.update(first_seen=old['first_seen'] if old else now(), last_seen=now(), present=1, tool_version=TOOL, rulebook_version=RULEBOOK)
                    columns = list(row)
                    con.execute(f"INSERT INTO files({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) ON CONFLICT(path) DO UPDATE SET " + ','.join(f'{c}=excluded.{c}' for c in columns if c != 'first_seen'), tuple(row.values()))
                    stats['changed' if old else 'added'] += 1
                    log(con, run, 'file_changed' if old else 'file_added', identity, {'sha256': row['sha256'], 'version_id': row['version_id']})
                    if row['readable'] == 'failed':
                        stats['errors'] += 1
                        queue(con, run, 'extraction_failure', identity, {'error': row['extraction_error'], 'sha256': row['sha256']})
            for error in walk_errors:
                stats['errors'] += 1
                queue(con, run, 'walk_failure', str(root), {'error': str(error)})
            if not walk_errors:
                for old in con.execute('SELECT * FROM files WHERE root=? AND present=1', (str(root),)).fetchall():
                    if old['path'] not in seen and not omitted(Path(old['path'])):
                        con.execute('UPDATE files SET present=0 WHERE path=?', (old['path'],))
                        stats['missing'] += 1
                        log(con, run, 'file_missing', old['path'], {'source_deleted_by_inventory': False})
        if stats['added'] or stats['changed'] or stats['missing']:
            proposed_groups(con, run)
        log(con, run, 'scan_complete', dump(list(map(str, roots))), stats)
    export(db_path, output)
    return stats


def propose_nabla(db_path, version_id, proposal):
    core = atlas()
    record = core.parse_input(proposal).to_dict()
    decoded = core.decode(record['address'])
    if not decoded['hash_valid']:
        raise ValueError('Nabla signature did not round-trip')
    classifier = proposal.get('classifier', '').strip()
    if not classifier or proposal.get('protocol_version') != PROTOCOL:
        raise ValueError('classifier and exact protocol_version are required')
    run = uuid.uuid4().hex
    with connect(db_path) as con:
        old = con.execute('SELECT * FROM nabla WHERE version_id=?', (version_id,)).fetchone()
        if not old:
            raise ValueError('Unknown version')
        kind = con.execute('SELECT record_type FROM works WHERE work_id=?', (old['work_id'],)).fetchone()[0]
        if kind != 'work':
            raise ValueError('Nabla work classification is not applicable to '+kind+' records')
        if old['status'] == 'approved':
            raise ValueError('Approved Nabla metadata is preserved; proposal cannot overwrite it')
        if proposal.get('source_sha256') != old['source_sha256']:
            raise ValueError('Proposal must bind this version source_sha256')
        if old['record_json'] == dump(record) and old['classifier'] == classifier:
            return record
        values = {**record['filing'], **record['vector'], 'signature': record['hash'], 'address': record['address'],
                  'filename_safe': record['filename_safe'], 'confidence_json': dump(record['confidence_by_variable']),
                  'decode_sentence': 'Dominant: '+', '.join(decoded['dominant'])+'; absent: '+', '.join(decoded['absent'])+'.',
                  'record_json': dump(record), 'classifier': classifier, 'classified_at': now(), 'status': 'proposed'}
        con.execute('UPDATE nabla SET '+','.join(f'"{c}"=?' for c in values)+' WHERE version_id=?', (*values.values(), version_id))
        queue(con, run, 'nabla_vector', version_id, {'record': record, 'classifier': classifier, 'source_sha256': old['source_sha256'], 'protocol_version': PROTOCOL})
        log(con, run, 'nabla_proposed', version_id, {'address': record['address'], 'classifier': classifier})
    return record


def set_record_type(db_path, work_id, record_type, *, ruled_by, reason):
    """Apply an explicit human grouping ruling, retaining every ID and source."""
    if record_type not in {'work', 'infrastructure', 'index'}:
        raise ValueError('Unknown record type')
    if not ruled_by.strip() or not reason.strip():
        raise ValueError('Human authority and ruling reason are required')
    run = uuid.uuid4().hex
    with connect(db_path) as con:
        old = con.execute('SELECT * FROM works WHERE work_id=?', (work_id,)).fetchone()
        if not old:
            raise ValueError('Unknown registry ID')
        if old['record_type'] == record_type:
            return {'work_id': work_id, 'record_type': record_type, 'changed': False}
        ruling = {'by': ruled_by, 'reason': reason, 'at': now(), 'from': old['record_type'], 'to': record_type}
        con.execute('UPDATE works SET record_type=?,record_type_ruling_json=?,tool_version=? WHERE work_id=?',
                    (record_type, dump(ruling), TOOL, work_id))
        versions = [r[0] for r in con.execute('SELECT version_id FROM versions WHERE work_id=?', (work_id,))]
        subjects = {work_id, *versions}
        for review in con.execute("SELECT * FROM review_queue WHERE kind IN ('work','version','nabla','nabla_vector')").fetchall():
            if review['subject'] not in subjects:
                continue
            status = ('resolved_by_record_type' if record_type != 'work' and review['status'] == 'pending'
                      else 'pending' if record_type == 'work' and review['status'] == 'resolved_by_record_type' else review['status'])
            if status != review['status']:
                con.execute('UPDATE review_queue SET status=? WHERE review_id=?', (status, review['review_id']))
                log(con, run, 'review_status_changed', review['review_id'], {'before': review['status'], 'after': status, 'ruling': ruling})
        if record_type == 'work':
            con.execute("UPDATE nabla SET status='unset' WHERE work_id=? AND status='not_applicable'", (work_id,))
        else:
            # Retain supplied/approved vectors; only unset placeholders become N/A.
            con.execute("UPDATE nabla SET status='not_applicable' WHERE work_id=? AND status='unset'", (work_id,))
        log(con, run, 'record_type_ruled', work_id, {'ruling': ruling, 'version_ids_retained': versions,
            'source_files_changed': False, 'canon_status_changed': False})
    return {'work_id': work_id, 'record_type': record_type, 'changed': True}


def write_if_changed(path, content):
    encoded = content.encode('utf-8')
    if not path.exists() or path.read_bytes() != encoded:
        path.write_bytes(encoded)


def export(db_path, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        works = [dict(r) for r in con.execute('SELECT * FROM works ORDER BY id')]
        files = [dict(r) for r in con.execute('SELECT * FROM files ORDER BY path')]
        nabla = {r['version_id']: dict(r) for r in con.execute('SELECT * FROM nabla')}
        versions = [dict(r) for r in con.execute('SELECT * FROM versions ORDER BY created_at,version_id')]
        reviews = [dict(r) for r in con.execute("SELECT * FROM review_queue WHERE status='pending' ORDER BY kind,subject")]
    finally:
        con.close()
    work_exports = []
    work_count = sum(w['record_type'] == 'work' for w in works)
    lines = ['# Stage 1 — Registry master', '', 'Generated from SQLite. Work/version groupings remain proposals unless explicitly ruled; record-type rulings are shown separately and do not set canon status.',
             '', 'Nabla: UNSET means no semantic classification has been supplied; no vector or signature is invented.', '', FIREWALL, '',
             f"{len(files)} physical file records · {work_count} proposed works · {sum(w['record_type'] == 'infrastructure' for w in works)} infrastructure · {sum(w['record_type'] == 'index' for w in works)} index · {len(versions)} retained version records · {len(reviews)} pending review items.", '',
             '## Works', '',
             '| Work ID | Display code | Preferred title (proposed) | Version | Nabla address | Review |', '|---|---|---|---|---|---|']
    def cell(value):
        return str(value if value is not None else '').replace('|', '\\|').replace('\n', ' ')
    for work in works:
        members = [v for v in versions if v['work_id'] == work['work_id']]
        addresses = []
        for version in members:
            n = nabla[version['version_id']]
            address = n['address'] or ('N/A — '+work['record_type'] if work['record_type'] != 'work' else 'UNSET — queued')
            addresses.append(address)
            if work['record_type'] == 'work':
                lines.append('| '+' | '.join(map(cell, [work['work_id'], work['display_code'], work['preferred_title'], version['version_id'], address, n['status']]))+' |')
        work_exports.append({**work, 'nabla_addresses_json': dump(addresses)})
    lines += ['', '## Infrastructure and indexes', '', '| Retained registry ID | Record type | Observed title | Human ruling |', '|---|---|---|---|']
    for work in works:
        if work['record_type'] != 'work':
            lines.append('| '+' | '.join(map(cell, [work['work_id'], work['record_type'], work['preferred_title'], work['record_type_ruling_json']]))+' |')
    lines += ['', '## Files', '', '| Path | Registry ID / version | Record type | Bytes | Readable | SHA-256 | Present |', '|---|---|---|---|---|---|---|']
    for row in files:
        version = next((v for v in versions if v['version_id'] == row['version_id']), {})
        record_type = next((w['record_type'] for w in works if w['work_id'] == version.get('work_id')), '')
        row['record_type'] = record_type
        lines.append('| '+' | '.join(map(cell, [row['path'], version.get('work_id', '')+' / '+str(row['version_id']), record_type, row['size'], row['readable'], row['sha256'], row['present']]))+' |')
    lines += ['', '## Pending review', '']
    for review in reviews:
        lines += [f"- **{review['kind']}** — {cell(review['subject'])}: {cell(review['evidence_json'])}"]
    lines += ['', '## Observation contract', '',
              'Unchanged files keep their existing records and exports byte-stable. last_seen is the last substantive file observation; each scan, including unchanged scans, is timestamped in change_log.',
              'Whitespace-normalized text equality is proposed version evidence, never byte identity. Unreadable and unsupported files remain listed. Historical versions remain retained after source edits.',
              'Series codes and titles are provisional. Published, verified, standing, canon_status and preferred-version fields remain unset. No source file is modified.', '']
    write_if_changed(output/'REGISTRY_MASTER.md', '\n'.join(lines))
    for name, rows in [('registry_works.csv', work_exports), ('registry_files.csv', files)]:
        stream = io.StringIO(newline='')
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        write_if_changed(output/name, stream.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=REPO/'_data/registry.sqlite')
    parser.add_argument('--output', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('scan').add_argument('roots', nargs='+')
    sub.add_parser('export')
    proposal = sub.add_parser('nabla-propose')
    proposal.add_argument('version_id')
    proposal.add_argument('input', type=Path)
    ruling = sub.add_parser('set-type')
    ruling.add_argument('work_id')
    ruling.add_argument('record_type', choices=['work', 'infrastructure', 'index'])
    ruling.add_argument('--by', required=True)
    ruling.add_argument('--reason', required=True)
    args = parser.parse_args(argv)
    if args.command == 'scan':
        print(dump(scan(args.roots, args.db, args.output)))
    elif args.command == 'nabla-propose':
        print(dump(propose_nabla(args.db, args.version_id, json.loads(args.input.read_text(encoding='utf-8')))))
        export(args.db, args.output or args.db.parent)
    elif args.command == 'set-type':
        print(dump(set_record_type(args.db, args.work_id, args.record_type, ruled_by=args.by, reason=args.reason)))
        export(args.db, args.output or args.db.parent)
    else:
        export(args.db, args.output or args.db.parent)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
