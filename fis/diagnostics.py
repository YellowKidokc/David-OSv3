"""Seven explainable checks consolidated from the preserved Rust kernel.

Uses the existing SHA-256 inventory instead of hashing a second time or changing
identity algorithms. These are review signals, never authority to mutate.
"""
import re
from collections import defaultdict
from pathlib import Path

MARKERS = {'.git', 'cargo.toml', 'package.json', 'requirements.txt', 'pyproject.toml'}


def symptoms(root, files, skipped=()):
    result = []
    folders = defaultdict(list)
    hashes = defaultdict(list)
    def add(code, severity, path, why):
        result.append({'id': code, 'severity': severity, 'path': str(path), 'evidence': why,
                       'source': 'fis-kernel-rust-v0.1 rules', 'action': 'review-only'})
    for row in files:
        p = Path(row['path'])
        folders[str(p.parent)].append(row)
        hashes[row['sha256']].append(row)
        if re.search(r'[_ ](?:final|copy)|\([12]\)|_v(?:[1-9]|1\d|20)(?:\D|$)', p.name, re.I):
            add('S02', 'medium', p, 'Version-like filename; content comparison required')
        if len(str(p)) > 200:
            add('N04', 'medium', p, 'Path exceeds 200 characters')
        if re.search(r'api_?key|secret|token|^\.env(?:\.|$)', p.name, re.I):
            add('I03', 'critical', p, 'Sensitive filename signal; not a rename candidate')
    folders.setdefault(str(Path(root)), [])
    for folder, rows in folders.items():
        markers = sorted(p.name for p in Path(folder).iterdir() if p.name.lower() in MARKERS)
        if markers:
            add('I01', 'critical', folder, 'Project-root markers: '+', '.join(markers))
        extensions = {Path(r['path']).suffix.lower() for r in rows}
        if len(extensions) > 8:
            add('S01', 'medium', folder, str(len(extensions))+' distinct extensions')
        if len(rows) > 200:
            add('S04', 'medium', folder, str(len(rows))+' direct files')
    for group in hashes.values():
        if len(group) > 1:
            add('C01', 'medium', group[0]['folder'], {'sha256': group[0]['sha256'],
                'paths': [r['path'] for r in group], 'meaning': 'Byte-identical; every location retained'})
    for row in skipped:
        if row.get('why') == 'secret file':
            add('I03', 'critical', row['path'], 'Secret excluded before reading bytes')
    return sorted(result, key=lambda r: (r['id'], r['path']))
