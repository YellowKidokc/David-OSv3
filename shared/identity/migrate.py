"""Apply an explicit identity assignment map, never rename or read source files.

python -m shared.identity.migrate assignments.json --db STATE/registry.sqlite
Dry-run is the default. --apply requires a mapping with reviewed_by and entries.
"""
import argparse
import json
from .registry import IdentityRegistry, document_id, location_key


def migrate(mapping, db, apply=False):
    if not isinstance(mapping, dict) or not isinstance(mapping.get('reviewed_by'), str) or not mapping['reviewed_by'].strip():
        raise ValueError('assignment map requires reviewed_by')
    entries = mapping.get('entries')
    if not isinstance(entries, list): raise ValueError('entries must be a list')
    plan, seen_paths, seen_names, seen_aliases = [], set(), set(), set()
    for entry in entries:
        public = document_id(entry['series'], entry['position'], entry['original_title'])
        path = location_key(entry['path'])
        if path in seen_paths or public in seen_names: raise ValueError('duplicate assignment in map')
        seen_paths.add(path); seen_names.add(public)
        for alias in entry.get('aliases', []):
            key = (alias['scheme'], alias['value'])
            if key in seen_aliases or not all(isinstance(v, str) and v.strip() for v in key):
                raise ValueError('duplicate or invalid alias')
            seen_aliases.add(key)
        plan.append({**entry, 'registry_id': public})
    if not apply:
        return {'applied': False, 'assignments': plan, 'source_files_changed': 0}
    registry = IdentityRegistry(db)
    con = registry._connect()
    try:
        with con:
            con.execute('BEGIN IMMEDIATE')
            result = []
            for entry in plan:
                ref = registry.assign(entry['path'], entry['series'], entry['position'], entry['original_title'], con=con)
                for alias in entry.get('aliases', []):
                    registry.alias(ref['uuid7'], alias['scheme'], alias['value'], con=con)
                result.append(ref)
            return {'applied': True, 'assignments': result, 'source_files_changed': 0}
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mapping')
    parser.add_argument('--db', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(json.loads(open(args.mapping, encoding='utf-8').read()), args.db, args.apply), indent=2))


if __name__ == '__main__': main()
