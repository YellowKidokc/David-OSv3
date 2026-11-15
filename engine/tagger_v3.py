"""Compatibility launcher for the single Tagger v3 implementation."""
from pathlib import Path
import argparse
import runpy
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'Theophysics_Tagger' / 'tools'


def legacy_arguments(argv):
    p = argparse.ArgumentParser(description='Legacy filetagger options forwarded to Tagger v3')
    p.add_argument('path', nargs='?')
    p.add_argument('--path', dest='path_opt')
    p.add_argument('--db', default='filecatalog.db')
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--quickhash', action='store_true')
    p.add_argument('--sidecar', action='store_true')
    p.add_argument('--force', action='store_true')
    args = p.parse_args(argv)
    source = args.path_opt or args.path
    if not source:
        p.error('give a source folder')
    db = Path(args.db).resolve()
    if db.is_file():
        with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as con:
            columns = {r[1] for r in con.execute('PRAGMA table_info(files)')}
        if columns and 'quick_hash' not in columns:
            # Preserve the legacy database byte-for-byte; never reinterpret its schema.
            db = db.with_name(db.stem + '.tagger3' + db.suffix)
            print(f'Legacy catalog preserved; Tagger v3 uses {db}', file=sys.stderr)
    out = ['scan', '--catalog', '--source', source, '--db', str(db), '--workers', str(args.workers),
           '--output', str(db.parent/'tagger3-exports'), '--tagged', str(db.parent/'tagger3-tagged')]
    if not args.quickhash: out.append('--full-hash')
    if args.sidecar: out.append('--write-sidecars')
    if args.force: out.append('--force')
    return out


def main(argv=None):
    args = legacy_arguments(sys.argv[1:] if argv is None else argv)
    sys.path.insert(0, str(TOOLS))
    from tagger3 import main as canonical_main
    return canonical_main(args)


def gui():
    sys.path.insert(0, str(TOOLS))
    runpy.run_path(str(TOOLS/'tagger3_gui.py'), run_name='__main__')


if __name__ == '__main__':
    raise SystemExit(main())
