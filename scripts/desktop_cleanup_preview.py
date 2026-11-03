"""Read-only desktop inventory and bounded exact-duplicate review. No mutations."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.desktop_merge_survey import survey, EXCLUDED

EXCLUDED.update({'.fis', '.claude', '.ts', 'dist', 'build', 'target', '.next', '.pytest_cache', '.gradle'})
GENERATED = {'.fisnote', 'fis.html', 'thumbs.db', 'desktop.ini', '.ds_store'}
FAMILIES = {
    'Documents': {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.odt'},
    'Text': {'.md', '.txt', '.rst'},
    'Images': {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.heic'},
    'Videos': {'.mp4', '.mkv', '.mov', '.webm', '.avi'},
    'Audio': {'.mp3', '.wav', '.m4a', '.flac', '.ogg'},
    'Archives': {'.zip', '.7z', '.rar', '.gz', '.tar'},
    'Scripts': {'.py', '.ps1', '.bat', '.cmd', '.ahk', '.js', '.sh'},
    'Shortcuts': {'.lnk', '.url'},
    'Executables': {'.exe', '.msi'},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--hash-gib', type=float, default=2)
    parser.add_argument('--hash-seconds', type=float, default=90)
    parser.add_argument('--inventory', type=Path, help='Reuse a saved metadata inventory; hashes still read live source bytes')
    args = parser.parse_args()
    root, out = args.root.resolve(strict=True), args.output.resolve()
    if out == root or root in out.parents:
        parser.error('Output must be outside desktop source tree')
    out.mkdir(parents=True, exist_ok=False)
    if args.inventory:
        data = json.loads(args.inventory.read_text(encoding='utf-8'))
        if Path(data['root']).resolve() != root:
            parser.error('Saved inventory belongs to another root')
        (out/'inventory-source.txt').write_text(str(args.inventory.resolve())+'\n', encoding='utf-8')
    else:
        data = survey(root)
        (out/'inventory.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    sizes, extensions = defaultdict(list), Counter()
    sorting = []
    for relative, info in data['files'].items():
        p = Path(relative)
        if any(part.lower() in EXCLUDED for part in p.parts[:-1]):
            continue
        if p.name.lower() in GENERATED or p.suffix.lower() == '.fisnote' or p.name.startswith('~$'):
            continue
        extensions[p.suffix.lower() or '(none)'] += 1
        # Code/project trees and nested folders are reviewed in context, not flattened.
        if len(p.parts) == 1:
            family = next((name for name, exts in FAMILIES.items() if p.suffix.lower() in exts), 'Review')
            sorting.append({'source': str(root/p), 'suggested_folder': family,
                            'status': 'proposal only; keep current filename'})
        if info['bytes'] > 0:
            sizes[info['bytes']].append(relative)
    candidates = [paths for paths in sizes.values() if len(paths)>1]
    candidates.sort(key=lambda paths: (not any(len(Path(p).parts)==1 for p in paths),
                                      -data['files'][paths[0]]['bytes']))
    hashed, failures, deferred = defaultdict(list), [], []
    consumed, started = 0, time.monotonic()
    for paths in candidates:
        for relative in paths:
            path = root/relative
            expected = data['files'][relative]
            if consumed+expected['bytes'] > args.hash_gib*1024**3 or time.monotonic()-started > args.hash_seconds:
                deferred.append(relative)
                continue
            try:
                before = path.stat()
                if (before.st_size, before.st_mtime_ns) != (expected['bytes'], expected['mtime_ns']):
                    raise ValueError('changed since inventory')
                with path.open('rb') as stream:
                    sha = hashlib.file_digest(stream, 'sha256').hexdigest()
                after = path.stat()
                if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                    raise ValueError('changed during hashing')
                consumed += before.st_size
                hashed[sha].append(relative)
            except (OSError, ValueError) as exc:
                failures.append({'path': relative, 'error': str(exc)})
    groups = []
    for sha, paths in hashed.items():
        if len(paths)>1:
            size = data['files'][paths[0]]['bytes']
            groups.append({'sha256':sha, 'bytes_each':size, 'extra_copy_bytes':size*(len(paths)-1),
                           'paths':paths, 'decision':'review required; no keeper selected'})
    groups.sort(key=lambda row: row['extra_copy_bytes'], reverse=True)
    result = {'root':str(root), 'created':datetime.now().isoformat(),
              'files':len(data['files']), 'logical_bytes':data['bytes'],
              'extensions':dict(extensions.most_common()), 'exact_duplicate_groups':groups,
              'potential_extra_copy_bytes':sum(g['extra_copy_bytes'] for g in groups),
              'hash_bytes_read':consumed, 'hash_deferred':deferred, 'hash_errors':failures,
              'excluded_directories':data['excluded'], 'inventory_errors':data['errors'],
              'source_mutations':False, 'scope':'bounded hash pass; excluded folders and deferred files are not cleared'}
    (out/'review.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with (out/'sort-proposals.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=['source','suggested_folder','status'])
        writer.writeheader(); writer.writerows(sorting)
    lines = ['# Desktop cleanup preview', '', f'Source: `{root}`', '',
             f"Inventoried {result['files']:,} files; {data['bytes']/1024**3:.2f} GiB logical size.",
             f"Verified {len(groups)} exact duplicate groups; {result['potential_extra_copy_bytes']/1024**2:.1f} MiB in extra copies.",
             f'{len(deferred)} files deferred by hash budget; {len(failures)} hash errors; {len(data["errors"])} inventory exceptions.',
             '', 'No files moved, renamed, deleted, or selected as keepers. Sizes are logical; links and storage deduplication may affect physical savings.',
             'Top-level sort proposals retain filenames; nested folder contents need context review.', '', '## Largest verified duplicate groups', '']
    for group in groups[:25]:
        lines.append(f"- {group['extra_copy_bytes']/1024**2:.2f} MiB extra copies; SHA-256 `{group['sha256']}`")
        lines.extend(f'  - `{p}`' for p in group['paths'][:10])
        if len(group['paths'])>10:
            lines.append(f"  - {len(group['paths'])-10} further paths in review.json")
    (out/'REVIEW.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['root','files','logical_bytes','potential_extra_copy_bytes']}, indent=2))
    print(f'Exact groups: {len(groups)}; deferred: {len(deferred)}; report: {out / "REVIEW.md"}', flush=True)


if __name__ == '__main__':
    main()
