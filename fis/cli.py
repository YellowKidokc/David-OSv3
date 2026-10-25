"""Short, offline commands. Default scans and plans never change source files."""
import argparse
import json
from pathlib import Path
from fis.index import Store
from fis import service, transaction
from fis.report import export


def main(argv=None):
    parser = argparse.ArgumentParser(prog='fis')
    parser.add_argument('--state', help='State/archive location outside selected folders, on same volume')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('scan', 'plan', 'report'):
        p = sub.add_parser(name)
        p.add_argument('folder')
    p = sub.add_parser('root')
    p.add_argument('folder')
    p.add_argument('--enable-html', action='store_true', help='Authorize automatic HTML generation and legacy-note archival')
    p = sub.add_parser('approve')
    p.add_argument('plan')
    p.add_argument('--hash', required=True)
    p.add_argument('--row', action='append')
    p = sub.add_parser('apply')
    p.add_argument('plan')
    p.add_argument('--approval', required=True)
    p = sub.add_parser('undo')
    p.add_argument('run')
    p.add_argument('--folder')
    p.add_argument('--preview', action='store_true')
    p = sub.add_parser('search')
    p.add_argument('query')
    sub.add_parser('history')
    p = sub.add_parser('export')
    p.add_argument('plan')
    p.add_argument('--format', choices=['html', 'csv'], default='html')
    p = sub.add_parser('serve')
    p.add_argument('--port', type=int, default=43107)
    p = sub.add_parser('crawl')
    p.add_argument('root')
    p.add_argument('--speed', choices=['Trickle', 'Background', 'Normal', 'Full'], default='Background')
    args = parser.parse_args(argv)
    store = Store(args.state)
    try:
        if args.command == 'scan':
            result = service.scan(store, args.folder)
        elif args.command in {'plan', 'report'}:
            result = service.make_plan(store, args.folder)
            result = {**result, 'rows': [{k:v for k,v in r.items() if k != 'content'} for r in result['rows']]}
        elif args.command == 'root':
            result = service.configure_root(store, args.folder, args.enable_html)
        elif args.command == 'approve':
            result = {'approval': transaction.approve(store, args.plan, args.hash, args.row)}
        elif args.command == 'apply':
            result = transaction.apply(store, args.plan, args.approval)
        elif args.command == 'undo':
            fn = transaction.rollback_preview if args.preview else transaction.undo
            result = fn(store, args.run, args.folder)
        elif args.command == 'search':
            result = store.search(args.query)
        elif args.command == 'history':
            result = store.all('run')
        elif args.command == 'export':
            print(export(store.get('plan', args.plan), args.format))
            return
        elif args.command == 'serve':
            from fis.web import serve
            serve(store, args.port)
            return
        elif args.command == 'crawl':
            from fis.crawler import Crawler
            result = Crawler(store).run(args.root, args.speed)
        print(json.dumps(result, indent=2))
    except (ValueError, PermissionError, OSError, RuntimeError) as error:
        parser.exit(2, str(error)+'\n')
