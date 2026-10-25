"""Bounded, nonmutating inventory. Hash identities never collapse path instances."""
import os
from pathlib import Path
from fis import gate
from fis.classify import classify
from fis.fingerprint import sha256_file
from fis.index import digest
from fis.diagnostics import symptoms
from fis.rename import propose
from fis.tag import tags

TEXT = {'.md', '.txt', '.rst', '.html', '.htm', '.py', '.js', '.ts', '.json', '.csv', '.yaml', '.lean'}


def inventory(root, config=None, recursive=True, on_file=None):
    config = config or gate.defaults()
    original = Path(root).absolute()
    if gate.unsafe(original, config):
        raise PermissionError(gate.unsafe(original, config))
    root = original.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    files, skipped = [], []
    walk_errors = []
    for folder, dirs, names in os.walk(root, followlinks=False, onerror=lambda e: walk_errors.append(str(e))):
        here = Path(folder)
        kept = []
        for name in sorted(dirs):
            reason = gate.unsafe(here/name, config)
            if reason:
                skipped.append({'path': str(here/name), 'why': reason})
            elif recursive:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            p = here/name
            reason = gate.unsafe(p, config)
            if reason or name == 'FIS.html' or name.endswith('.fisnote') or name in {'.fmeta', '.folder.fmeta'}:
                skipped.append({'path': str(p), 'why': reason or 'metadata sidecar'})
                continue
            try:
                before = p.stat()
                text = ''
                if p.suffix.lower() in TEXT:
                    with p.open('rb') as handle:
                        text = handle.read(64_000).decode('utf-8', errors='replace')
                sha = sha256_file(p)
                after = p.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise OSError('file changed during scan')
                legacy = ''
                note = p.with_name(p.name+'.fisnote')
                if note.is_file() and not gate.unsafe(note, config):
                    legacy = note.read_text(encoding='utf-8', errors='replace')
                tagging = tags(name, text, legacy, config['rulepacks'])
                row = {'id': digest(str(p)), 'path': str(p), 'relative': str(p.relative_to(root)),
                       'folder': str(here), 'sha256': sha, 'size': after.st_size,
                       'mtime_ns': after.st_mtime_ns, 'atime_ns': before.st_atime_ns,
                       'tags': tagging, 'classification': classify(p, tagging),
                       'rename': propose(p, text, after.st_mtime, config['rulepacks']),
                       'extraction': 'bounded-utf8' if p.suffix.lower() in TEXT else 'metadata-only',
                       'partial_text': after.st_size > 64000 or p.suffix.lower() not in TEXT}
                files.append(row)
                if on_file:
                    on_file(row)
            except (OSError, UnicodeError) as error:
                skipped.append({'path': str(p), 'why': str(error), 'error': True})
    skipped += [{'path': str(root), 'why': e, 'error': True} for e in walk_errors]
    return {'root': str(root), 'files': files, 'skipped': skipped,
            'symptoms': symptoms(root, files, skipped)}
