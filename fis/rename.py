"""Current hybrid filename grammar, reusing the existing renamer's pure helpers."""
import json
import re
from datetime import datetime
from pathlib import Path
from fis.naming_helpers import _clean, _match, _split_camel, _words

EXT_TYPES = {'.lean': 'LEA', '.py': 'SCR', '.ps1': 'SCR'}
LAW_STEM = re.compile(r'^law[_ -]*(\d{1,2})(?![0-9])[_ -]*(.*)$', re.I)


def _people(law):
    return {x.split()[0].lower() for x in [law.get('person')] + list(law.get('person_alt', [])) if x}


def _law(stem, laws):
    """Match a LAW_NN_... stem against the laws registry. Returns None, or a dict with the registry
    entry (None when NN is not in the registry), the leftover words, and a hold when the person named
    in the file belongs to a different law than the number says."""
    m = LAW_STEM.match(stem)
    if not m:
        return None
    n = int(m.group(1))
    rest = _clean(_split_camel(m.group(2))).split()
    entry = {l['n']: l for l in (laws or {}).get('laws', [])}.get(n)
    hold = ''
    if entry:
        mine = _people(entry)
        if mine and not mine & set(rest):
            others = sorted(l['n'] for l in laws['laws'] if l['n'] != n and _people(l) & set(rest))
            if others:
                hold = ('law-number: file says Law %02d but names %s, who is Law %s in the registry'
                        % (n, ', '.join(sorted(set(rest) & set().union(*(_people(l) for l in laws['laws'])))),
                           ' / '.join('%02d' % o for o in others)))
    return {'n': n, 'rest': rest, 'entry': entry, 'hold': hold}


def propose(path, text, mtime, packs=(), learned=None, laws=None):
    """learned: optional learned-tier vocabulary (docs/FIS_NAMING_SCHEMA.md). It is tried after the
    core and the packs, rejected rules are ignored, and a match is labelled as a provisional new class.
    laws: optional laws registry (docs/vocabulary-candidates/laws.registry.draft.json)."""
    rules = json.loads((Path(__file__).parent / 'data' / 'naming.json').read_text(encoding='utf-8'))
    for pack in packs:
        if pack != 'theophysics':
            raise ValueError('Unknown rule pack: ' + pack)
        extra = json.loads((Path(__file__).parent / 'data' / (pack+'.json')).read_text(encoding='utf-8'))
        rules['domains'] = extra['domains'] + rules['domains']
    new_codes = set()
    if learned:
        for table in ('domains', 'types', 'status'):
            kept = [r for r in learned.get(table, []) if r.get('provenance', {}).get('state') != 'rejected']
            taken = {r['code'] for r in rules[table]}
            kept = [r for r in kept if r['code'] not in taken]
            new_codes |= {r['code'] for r in kept}
            rules[table] = rules[table] + kept
    have = {t: {r['code'] for r in rules[t]} for t in ('domains', 'types')}
    p = Path(path)
    title = next((s[2:] for s in text.splitlines() if s.startswith('# ')), '')
    name, heading, body = _clean(_split_camel(p.stem)), _clean(title), _clean(text[:4000])
    why = []
    domain = _match(rules['domains'], name, heading, body)
    law = _law(p.stem, laws)
    # A file named LAW_NN_... belongs to the Ten Laws whatever its title keywords say.
    if law and 'LAW' in have['domains']:
        domain = ('LAW', "LAW ← filename starts with LAW_NN", 0.35)
    typ = _match(rules['types'], name, heading, '')
    if not typ and law:
        code = 'EXP' if 'expansion' in law['rest'] else 'CRD'
        if code in have['types'] and not (p.suffix.lower() in EXT_TYPES and EXT_TYPES[p.suffix.lower()] in have['types']):
            typ = (code, code+(' ← expansion in name' if code == 'EXP' else ' ← law document'), 0.2)
    if not typ and EXT_TYPES.get(p.suffix.lower()) in have['types']:
        code = EXT_TYPES[p.suffix.lower()]
        typ = (code, code+' ← '+p.suffix.lower()+' extension', 0.2)
    status = _match(rules['status'], name, heading, '')
    words, reasons = _words(p.stem, title, rules)
    if law and law['entry'] and not law['hold']:
        base = re.sub(r'^law_\d+_', '', law['entry']['short'].lower())
        known = set(base.split('_')) | set(rules['drop_words']) | {'expansion'}
        extra = [w for w in law['rest'] if w not in known and len(w) > 1]
        words = '_'.join(['l%02d' % law['n']] + base.split('_') + extra)
        draft = str(laws.get('status', '')).upper().startswith('DRAFT')
        reasons = ['registry: Law %02d = %s%s' % (law['n'], law['entry']['short'], ' (draft registry)' if draft else '')]
    for label, hit in [('domain', domain), ('type', typ), ('lifecycle', status)]:
        evidence = hit[1] if hit else 'No clue; configured fallback'
        if hit and hit[0] in new_codes:
            evidence += ' [new class, provisional]'
        why.append({'rule': 'hybrid-v20261014.'+label, 'evidence': evidence})
    if law and law['hold']:
        why.append({'rule': 'laws-registry', 'evidence': law['hold']})
    why += [{'rule': 'readable-words', 'evidence': r} for r in reasons]
    codes = [domain[0] if domain else rules['domain_fallback'], typ[0] if typ else rules['type_fallback'],
             status[0] if status else rules['status_fallback']]
    suffix = '__'+datetime.fromtimestamp(mtime).strftime('%Y%m%d')+'__'+codes[2]+p.suffix
    prefix = codes[0]+'__'+codes[1]+'__'
    words = words[:rules['max_length']-len(prefix)-len(suffix)].rstrip('_')
    proposed = prefix+words+suffix
    if re.match(r'^[A-Z]{3}__[A-Z]{3}__.*__\d{8}__[A-Z]{2}$', p.stem):
        proposed = p.name
    confidence = round(.3+(domain[2] if domain else 0)+(typ[2] if typ else 0), 2)
    result = {'name': proposed, 'confidence': confidence,
              'why': why, 'rulepacks': list(packs), 'approval': 'required'}
    if law and law['hold']:
        result['confidence'] = 0.3
        result['hold'] = law['hold']
    # Linked markdown remains a proposal for review; this first executor does not rewrite document bodies.
    return result
