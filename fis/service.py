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
from fis import preference


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


def make_plan(store, root, recursive=True, html=True, template='fable', on_file=None, scanned=None):
    result = scanned if scanned is not None else scan(store, root, recursive, on_file)
    if scanned is not None:
        if result['root'] != str(Path(root).resolve()):
            raise ValueError('Inventory does not match selected root')
        for record in result['files']:
            store.record(record)
        store.put('scan', result['root'], result)
    if any(x.get('error') for x in result['skipped']):
        raise ValueError('Incomplete scan: review unreadable/changed sources before planning')
    rows = []
    learners = preference.ensemble(store)
    # Gather links once; never reread every Markdown file for every proposal.
    import re
    from urllib.parse import unquote
    references = set()
    partial_links = False
    for other in result['files']:
        if Path(other['path']).suffix.lower() == '.md':
            with Path(other['path']).open(encoding='utf-8', errors='replace') as handle:
                body = handle.read(1_000_001)
            partial_links = partial_links or len(body) > 1_000_000
            for wiki, link in re.findall(r'\[\[([^\]|#]+)|\]\(([^)\s]+)', body):
                target = unquote((wiki or link).split('#')[0]).replace('\\', '/')
                references.add(Path(target).name.casefold())
    targets = Counter(str(Path(r['path']).with_name(r['rename']['name'])).casefold() for r in result['files'])
    for r in result['files']:
        target = str(Path(r['path']).with_name(r['rename']['name']))
        if r['path'] != target:
            flag = 'collision' if targets[target.casefold()] > 1 or Path(target).exists() else ''
            # Link rewrites are deliberately separate proposals. Hold linked Markdown instead of breaking references.
            if Path(r['path']).suffix.lower() == '.md':
                p = Path(r['path'])
                if partial_links or p.stem.casefold() in references or p.name.casefold() in references:
                    flag = 'linked-source: rename held until reference migration is approved'
            rows.append({'id': 'rename-'+r['id'], 'kind': 'rename', 'path': r['path'], 'target': target,
                         'sha256': r['sha256'], 'folder': r['folder'], 'why': r['rename']['why'],
                         'flag': flag, 'file': r})
            rows[-1]['preference'] = preference.prediction(learners, rows[-1])
    rows.sort(key=lambda row: (bool(row['flag']), -row['preference']['score'], row['path'].casefold()))
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
                         'files': sources,
                         'sources': [{'path': r['path'], 'sha256': r['sha256']} for r in sources],
                         'content': content, 'template': template, 'why': [{'rule': 'html-folder-memory',
                         'evidence': 'Full legacy bytes embedded; originals move to run archive'}], 'flag': ''})
    plan = {'id': uid(), 'root': result['root'], 'created': time.time(), 'rows': rows,
            'skipped': result['skipped'], 'symptoms': result['symptoms'],
            'pipeline': ['tag', 'classify', 'rename-proposal', 'html-sidecar']}
    plan['hash'] = plan_hash(plan)
    store.put('plan', plan['id'], plan)
    return plan


def edit_plan(store, plan_id, expected_hash, edits):
    """Create a fresh immutable plan; editing never reuses an approval."""
    from fis.transaction import verify_plan
    import copy
    import re
    old = store.get('plan', plan_id)
    verify_plan(old)
    if old['hash'] != expected_hash:
        raise ValueError('Plan changed; reload before editing')
    plan = copy.deepcopy(old)
    known = {r['id'] for r in plan['rows'] if r['kind'] == 'rename'}
    if not set(edits) <= known:
        raise ValueError('Only rename rows can be edited')
    for row in plan['rows']:
        if row['id'] not in edits:
            continue
        name = edits[row['id']].strip()
        if (not name or name.endswith((' ', '.')) or name.startswith('.') or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or len(name) > 150 or
            name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *{'COM'+str(i) for i in range(1,10)}, *{'LPT'+str(i) for i in range(1,10)}}):
            raise ValueError('Invalid Windows filename: '+name)
        if Path(name).suffix.lower() != Path(row['path']).suffix.lower():
            raise ValueError('Changing extensions is not a rename correction')
        row['original_target'] = row.get('original_target', row['target'])
        row['target'] = str(Path(row['path']).with_name(name))
        row['file']['rename']['name'] = name
        row['why'].append({'rule': 'human-name-correction', 'evidence': name})
        # Never clear dependency/link holds through a text edit.
        if row['flag'] == 'collision':
            row['flag'] = ''
        if Path(row['target']).exists():
            row['flag'] = 'collision'
    counts = Counter(r['target'].casefold() for r in plan['rows'] if r['kind']=='rename')
    for row in plan['rows']:
        if row['kind']=='rename' and counts[row['target'].casefold()] > 1:
            row['flag'] = 'collision'
    corrections = {r['path']: r['file'] for r in plan['rows'] if r['kind']=='rename'}
    for row in plan['rows']:
        if row['kind']=='html':
            if 'files' not in row:
                raise ValueError('Recreate this older plan before editing its names')
            row['files'] = [corrections.get(r['path'], r) for r in row['files']]
            row['content'] = render(row['folder'], row['files'], row['legacy'], row['template'], 'RUN_ID_PLACEHOLDER')
    plan['id'], plan['created'], plan['parent_plan'] = uid(), time.time(), old['id']
    plan['hash'] = plan_hash(plan)
    store.put('plan', plan['id'], plan)
    return plan
