"""Same feature contract as the existing preference engines, with name-style clues."""
import re
from pathlib import Path


def feature_key(proposal):
    return tuple(proposal.get(k, default) for k, default in
                 [('domain_code', 'GEN'), ('ct_code', 'DOC'), ('status_code', 'AC')])


def proposal(row, name=None):
    name = name or Path(row['target']).name
    fields = Path(name).stem.split('__')
    domain, ct, status = (fields[0], fields[1], fields[-1]) if len(fields) >= 5 else ('CUSTOM', 'CUSTOM', 'AC')
    tags = [t['tag'] for t in row.get('file', {}).get('tags', [])]
    words = fields[2] if len(fields) >= 5 else Path(name).stem
    tags += ['word_'+w.lower() for w in re.findall(r'[a-zA-Z]{2,}', words)[:12]]
    tags += ['style_readable', 'separator_'+('underscore' if '_' in words else 'space' if ' ' in words else 'plain')]
    return {'proposed_name': name, 'domain_code': domain, 'ct_code': ct,
            'status_code': status, 'tags': tags}
