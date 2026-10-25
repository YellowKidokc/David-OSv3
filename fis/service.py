"""One API for CLI, crawler and browser; sources mutate only through transaction."""
import time
from collections import Counter
from pathlib import Path
from fis import gate
from fis.fingerprint import sha256_file
from fis.index import digest, uid
from fis.scan import inventory
from fis.sidecar import legacy_notes, render
from fis.transaction import plan_hash


def configure_root(store, root, html=False):
    path = Path(root).absolute()
    config = gate.policy(store)
    reason = gate.unsafe(path, config)
    if reason:
        raise PermissionError(reason)
    root = str(path.resolve())
    if not Path(root).is_dir():
        raise NotADirectoryError(root)
    if gate.under(store.home, root) or gate.under(root, store.home):
        raise PermissionError('State must be outside selected roots')
    if root not in config['roots']:
        config['roots'].append(root)
    if html and root not in config['html_roots']:
        config['html_roots'].append(root)
    store.put('config', 'main', config)
    return config


def scan(store, root, recursive=True, on_file=None):
    result = inventory(root, gate.policy(store), recursive, on_file)
    if gate.under(store.home, result['root']):
        raise PermissionError('State must be outside source')
    for row in result['files']:
        store.record(row)
    store.put('scan', result['root'], result)
    return result


def make_plan(store, root, recursive=True, html=True, template='fable', on_file=None):
    result = scan(store, root, recursive, on_file)
    if any(x.get('error') for x in result['skipped']):
        raise ValueError('Incomplete scan: review unreadable/changed sources before planning')
    rows = []
    targets = Counter(str(Path(r['path']).with_name(r['rename']['name'])).casefold() for r in result['files'])
    for r in result['files']:
        target = str(Path(r['path']).with_name(r['rename']['name']))
        if r['path'] != target:
            flag = 'collision' if targets[target.casefold()] > 1 or Path(target).exists() else ''
            # Link rewrites are deliberately separate proposals. Hold linked Markdown instead of breaking references.
            if Path(r['path']).suffix.lower() == '.md':
                for other in result['files']:
                    if Path(other['path']).suffix.lower() == '.md':
                        with Path(other['path']).open(encoding='utf-8', errors='replace') as handle:
                            body = handle.read(1_000_000)
                        if '[['+Path(r['path']).stem in body or Path(r['path']).name in body:
                            flag = 'linked-source: rename held until reference migration is approved'
                            break
            rows.append({'id': 'rename-'+r['id'], 'kind': 'rename', 'path': r['path'], 'target': target,
                         'sha256': r['sha256'], 'folder': r['folder'], 'why': r['rename']['why'],
                         'flag': flag, 'file': r})
    folders = {str(Path(result['root']))}
    folders.update(r['folder'] for r in result['files'])
    if recursive:
        import os
        for here, dirs, _ in os.walk(result['root'], followlinks=False):
            dirs[:] = [d for d in dirs if not gate.unsafe(Path(here)/d, gate.policy(store))]
            folders.add(str(Path(here)))
    if html:
        for folder in sorted(folders):
            notes = legacy_notes(folder)
            sources = [r for r in result['files'] if r['folder'] == folder]
            p = Path(folder)/'FIS.html'
            if p.is_symlink():
                raise PermissionError('HTML destination is a link')
            content = render(folder, sources, notes, template, 'RUN_ID_PLACEHOLDER')
            rows.append({'id': 'html-'+digest(folder), 'kind': 'html', 'path': str(p), 'folder': folder,
                         'before_hash': sha256_file(p) if p.is_file() else None, 'legacy': notes,
                         'sources': [{'path': r['path'], 'sha256': r['sha256']} for r in sources],
                         'content': content, 'template': template, 'why': [{'rule': 'html-folder-memory',
                         'evidence': 'Full legacy bytes embedded; originals move to run archive'}], 'flag': ''})
    plan = {'id': uid(), 'root': result['root'], 'created': time.time(), 'rows': rows,
            'skipped': result['skipped'], 'pipeline': ['tag', 'classify', 'rename-proposal', 'html-sidecar']}
    plan['hash'] = plan_hash(plan)
    store.put('plan', plan['id'], plan)
    return plan
