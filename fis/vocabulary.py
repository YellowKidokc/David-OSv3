"""Learned naming vocabulary and the suggestion counter (see docs/FIS_NAMING_SCHEMA.md).

Two tiers: the shipped core (data/naming.json, data/theophysics.json) is never edited; the learned
tier is data/vocabulary.learned.json (shipped, provisional) layered under <state>/vocabulary.user.json
(written here). Terms that recur in files that fell back to GEN/ART are counted by distinct file and
folder; past a threshold a provisional rule is created. A person confirms or rejects it later.
"""
import json
import re
import time
from pathlib import Path

DATA = Path(__file__).parent / 'data'
USER = 'vocabulary.user.json'
LEDGER = 'vocabulary.candidates.json'
LAWS = 'laws.registry.json'
SHAPES = {'domains': r'[A-Z]{3}', 'types': r'[A-Z]{3}', 'status': r'[A-Z]{2}'}
FALLBACKS = {'GEN', 'ART', 'AC'}
STATES = {'provisional', 'confirmed', 'rejected'}
THRESHOLDS = {'domains': (15, 3), 'types': (15, 3)}    # (distinct files, distinct folders)
MAX_PROMOTIONS_PER_SCAN = 5
MAX_REMEMBERED = 200
STOP = set('''the and for with from this that into over under about after before between through during
file files note notes copy final draft part main data text untitled document documents new old
version versions'''.split())


def validate(vocab):
    """Return a list of problems; an empty list means the vocabulary is safe to load."""
    if not isinstance(vocab, dict):
        return ['not an object']
    problems = []
    for table, shape in SHAPES.items():
        rules = vocab.get(table, [])
        if not isinstance(rules, list):
            problems.append(table + ': not a list')
            continue
        seen = set()
        for rule in rules:
            code = rule.get('code') if isinstance(rule, dict) else None
            if not isinstance(code, str) or not re.fullmatch(shape, code):
                problems.append('%s: bad code %r' % (table, code))
                continue
            if code in seen:
                problems.append('%s: duplicate code %s' % (table, code))
            seen.add(code)
            words = rule.get('words')
            if not isinstance(words, list) or not words or not all(isinstance(w, str) and len(w) >= 2 for w in words):
                problems.append('%s %s: words must be a non-empty list of strings' % (table, code))
            state = rule.get('provenance', {}).get('state', 'provisional')
            if state not in STATES:
                problems.append('%s %s: bad state %r' % (table, code, state))
    return problems


def _read(path):
    if not Path(path).is_file():
        return None, []
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        return None, ['%s ignored: %s' % (Path(path).name, error)]
    problems = validate(data)
    if problems:
        return None, ['%s ignored: %s' % (Path(path).name, '; '.join(problems[:5]))]
    return data, []


def _merge(base, over):
    """Rules in `over` replace same-code rules in `base`; new codes are appended."""
    out = {t: list(base.get(t, [])) for t in SHAPES}
    for table in SHAPES:
        for rule in (over or {}).get(table, []):
            out[table] = [r for r in out[table] if r['code'] != rule['code']] + [rule]
    return out


def layers(home):
    """What propose() needs: {'learned': merged vocabulary or None, 'laws': registry or None, 'warnings': [...]}."""
    shipped, warn1 = _read(DATA / 'vocabulary.learned.json')
    user, warn2 = _read(Path(home) / USER)
    learned = _merge(shipped or {}, user or {}) if (shipped or user) else None
    laws, warn3 = _read_laws(Path(home) / LAWS)
    if laws is None:
        laws, warn4 = _read_laws(DATA / LAWS)
        warn3 += warn4
    return {'learned': learned, 'laws': laws, 'warnings': warn1 + warn2 + warn3}


def _read_laws(path):
    if not Path(path).is_file():
        return None, []
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        assert isinstance(data.get('laws'), list) and all(isinstance(l.get('n'), int) and l.get('short') for l in data['laws'])
        return data, []
    except (OSError, ValueError, AssertionError, AttributeError) as error:
        return None, ['%s ignored: %s' % (Path(path).name, error)]


def _write(path, data):
    problems = validate(data)
    if problems:
        raise ValueError('Refusing to write an invalid vocabulary: ' + '; '.join(problems[:3]))
    # Small state file written in place: a torn write is caught by validate() on the next load.
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def _core_codes():
    taken = set(FALLBACKS)
    for name in ('naming.json', 'theophysics.json'):
        data = json.loads((DATA / name).read_text(encoding='utf-8'))
        for table in SHAPES:
            taken |= {r['code'] for r in data.get(table, [])}
    return taken


def _core_words():
    words = set()
    for name in ('naming.json', 'theophysics.json'):
        data = json.loads((DATA / name).read_text(encoding='utf-8'))
        for table in SHAPES:
            for rule in data.get(table, []):
                words |= {w.lower() for w in rule['words']}
    return words


def derive_code(term, taken, length=3):
    """Pick an unused capital-letter code from a term: first letters, then first plus consonants, then letter walks."""
    letters = re.sub(r'[^a-z]', '', term.lower())
    if len(letters) < length:
        letters = (letters + 'xxx')[:length]
    first, rest = letters[0], letters[1:]
    consonants = ''.join(c for c in rest if c not in 'aeiou')
    pool = [letters[:length], first + consonants[:length - 1], first + rest[:1] + rest[-1:]]
    pool += [first + a + b for a in rest for b in rest]
    for candidate in pool:
        code = candidate.upper()[:length]
        if len(code) == length and code not in taken:
            return code
    raise ValueError('No free code for ' + term)


def _tokens(name):
    """Title words of a proposed name, DOMAIN__TYPE__words__DATE__STATUS.ext."""
    parts = name.rsplit('.', 1)[0].split('__')
    if len(parts) < 5:
        return None, None, []
    words = [w for w in parts[2].split('_') if w.isalpha() and len(w) > 3 and w not in STOP]
    return parts[0], parts[1], words


def observe(home, result):
    """Count recurring unmatched terms in a scan result and promote any that pass a threshold.
    Returns the list of provisional rules created. Never touches the scanned folders."""
    home = Path(home)
    path = home / LEDGER
    try:
        ledger = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    except (OSError, ValueError):
        ledger = {}
    ledger.setdefault('domains', {})
    ledger.setdefault('types', {})
    for row in result.get('files', []):
        domain, typ, words = _tokens(row['rename']['name'])
        for table, active in (('domains', domain == 'GEN'), ('types', typ == 'ART')):
            if not active:
                continue
            for word in set(words):
                entry = ledger[table].setdefault(word, {'files': [], 'folders': [], 'first': time.time()})
                for key, value in (('files', row['id']), ('folders', row['folder'])):
                    if value not in entry[key] and len(entry[key]) < MAX_REMEMBERED:
                        entry[key].append(value)
    created = _promote(home, ledger)
    for table in ledger:
        # Keep the ledger small: drop one-off terms that have not repeated.
        ledger[table] = {t: e for t, e in ledger[table].items() if len(e['files']) > 1}
    path.write_text(json.dumps(ledger), encoding='utf-8')
    return created


def _promote(home, ledger):
    user, _ = _read(home / USER)
    user = user or {'id': 'fis.learned.user', 'tier': 'learned', 'domains': [], 'types': [], 'status': []}
    taken = _core_codes() | {r['code'] for t in SHAPES for r in user.get(t, [])}
    shipped, _ = _read(DATA / 'vocabulary.learned.json')
    taken |= {r['code'] for t in SHAPES for r in (shipped or {}).get(t, [])}
    known = _core_words()
    for t in SHAPES:
        for r in list((shipped or {}).get(t, [])) + user.get(t, []):
            known |= {w.lower() for w in r['words']}
    created = []
    for table in ('domains', 'types'):
        need_files, need_folders = THRESHOLDS[table]
        ranked = sorted(ledger.get(table, {}).items(), key=lambda kv: -len(kv[1]['files']))
        for term, entry in ranked:
            if len(created) >= MAX_PROMOTIONS_PER_SCAN:
                break
            if len(entry['files']) < need_files or len(entry['folders']) < need_folders:
                continue
            if any(term.startswith(k[:6]) for k in known if len(k) >= 4) or term in known:
                continue
            code = derive_code(term, taken)
            taken.add(code)
            rule = {'code': code, 'label': term, 'words': [term],
                    'provenance': {'created_by': 'counter', 'state': 'provisional',
                                   'created': time.strftime('%Y-%m-%d'), 'distinct_files': len(entry['files']),
                                   'distinct_folders': len(entry['folders']),
                                   'examples': [],
                                   'reason': 'Recurring term in files that fell back to %s' % ('GEN' if table == 'domains' else 'ART')}}
            user[table].append(rule)
            known.add(term)
            created.append({'table': table, **rule})
    if created:
        _write(home / USER, user)
    return created


def _set_state(home, code, state):
    home = Path(home)
    user, _ = _read(home / USER)
    user = user or {'id': 'fis.learned.user', 'tier': 'learned', 'domains': [], 'types': [], 'status': []}
    shipped, _ = _read(DATA / 'vocabulary.learned.json')
    for table in SHAPES:
        rule = next((r for r in user.get(table, []) if r['code'] == code), None)
        if rule is None:
            rule = next((r for r in (shipped or {}).get(table, []) if r['code'] == code), None)
            if rule is None:
                continue
            rule = json.loads(json.dumps(rule))
            user.setdefault(table, []).append(rule)
        rule.setdefault('provenance', {'created_by': 'user'})['state'] = state
        _write(home / USER, user)
        return rule
    raise KeyError('No learned rule with code ' + code)


def confirm(home, code):
    return _set_state(home, code, 'confirmed')


def reject(home, code):
    return _set_state(home, code, 'rejected')


def status(home):
    """Provisional rules awaiting a decision, plus the strongest pending candidates."""
    merged = layers(home)
    pending = [{'table': t, 'code': r['code'], 'words': r['words'], **r.get('provenance', {})}
               for t in SHAPES for r in (merged['learned'] or {}).get(t, [])
               if r.get('provenance', {}).get('state', 'provisional') == 'provisional']
    path = Path(home) / LEDGER
    ledger = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    near = sorted(({'table': t, 'term': k, 'files': len(e['files']), 'folders': len(e['folders'])}
                   for t in ('domains', 'types') for k, e in ledger.get(t, {}).items()),
                  key=lambda x: -x['files'])[:20]
    return {'provisional': pending, 'candidates': near, 'warnings': merged['warnings']}
