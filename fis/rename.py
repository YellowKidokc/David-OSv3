"""Current hybrid filename grammar, reusing the existing renamer's pure helpers."""
import json
import re
from datetime import datetime
from pathlib import Path
from fis.naming_helpers import _clean, _match, _words


def propose(path, text, mtime, packs=()):
    rules = json.loads((Path(__file__).parent / 'data' / 'naming.json').read_text(encoding='utf-8'))
    for pack in packs:
        if pack != 'theophysics':
            raise ValueError('Unknown rule pack: ' + pack)
        extra = json.loads((Path(__file__).parent / 'data' / (pack+'.json')).read_text(encoding='utf-8'))
        rules['domains'] = extra['domains'] + rules['domains']
    p = Path(path)
    title = next((s[2:] for s in text.splitlines() if s.startswith('# ')), '')
    name, heading, body = _clean(p.stem), _clean(title), _clean(text[:4000])
    why = []
    domain = _match(rules['domains'], name, heading, body)
    typ = _match(rules['types'], name, heading, '')
    status = _match(rules['status'], name, heading, '')
    words, reasons = _words(p.stem, title, rules)
    for label, hit in [('domain', domain), ('type', typ), ('lifecycle', status)]:
        why.append({'rule': 'hybrid-v20261014.'+label, 'evidence': hit[1] if hit else 'No clue; configured fallback'})
    why += [{'rule': 'readable-words', 'evidence': r} for r in reasons]
    codes = [domain[0] if domain else rules['domain_fallback'], typ[0] if typ else rules['type_fallback'],
             status[0] if status else rules['status_fallback']]
    suffix = '__'+datetime.fromtimestamp(mtime).strftime('%Y%m%d')+'__'+codes[2]+p.suffix
    prefix = codes[0]+'__'+codes[1]+'__'
    words = words[:rules['max_length']-len(prefix)-len(suffix)].rstrip('_')
    proposed = prefix+words+suffix
    if re.match(r'^[A-Z]{3}__[A-Z]{3}__.*__\d{8}__[A-Z]{2}$', p.stem):
        proposed = p.name
    # Linked markdown remains a proposal for review; this first executor does not rewrite document bodies.
    return {'name': proposed, 'confidence': round(.3+(domain[2] if domain else 0)+(typ[2] if typ else 0), 2),
            'why': why, 'rulepacks': list(packs), 'approval': 'required'}
