"""Local-only browser API with host/origin checks and a per-server request token."""
import json
import secrets
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from fis import gate, service, templates, transaction
from fis.crawler import Crawler, PRESETS
from fis.index import digest, uid
from fis.report import export
from fis import preference, review

STATIC = Path(__file__).parent/'static'


class API:
    def __init__(self, store):
        self.store = store
        self.crawler = Crawler(store)

    def state(self):
        return {'config': gate.policy(self.store), 'crawler': self.crawler.status(),
                'plans': review.summaries(self.store),
                'preferences': preference.stats(self.store),
                'background': self.store.get('background', 'status', {'status': 'manual', 'enabled': False}),
                'runs': self.store.all('run'), 'templates': templates.registry(self.store),
                'rules': templates.rules(self.store), 'candidates': self.store.all('candidate-rule'),
                'template_queue': [q for q in self.store.all('template-queue') if not q.get('resolved')],
                'conflicts': self.store.all('conflict'), 'health': self.store.all('health'),
                'presets': PRESETS}

    def action(self, data):
        action = data['action']
        s = self.store
        if action == 'scan':
            return service.scan(s, data['root'])
        if action == 'plan':
            return service.make_plan(s, data['root'], template=data.get('template', 'fable'))
        if action == 'root-preview':
            root = str(Path(data['root']).absolute())
            preview = {'root': root, 'enable_html': bool(data.get('html')), 'policy_hash': digest(gate.policy(s)),
                       'changes': ['Allow explicitly approved plans in this root'] +
                       (['Allow crawler to write FIS.html and move full legacy notes to the run archive. Never rename sources automatically.'] if data.get('html') else [])}
            preview['id'] = uid()
            s.put('root-preview', preview['id'], preview)
            return preview
        if action == 'root-approve':
            preview = s.get('root-preview', data['preview'])
            if not preview or preview['policy_hash'] != digest(gate.policy(s)):
                raise ValueError('Root policy changed; preview again')
            return service.configure_root(s, preview['root'], preview['enable_html'])
        if action == 'approve-apply':
            # Separate approval receipt and executor, one visible browser action.
            token = transaction.approve(s, data['plan'], data['hash'], data['rows'])
            return transaction.apply(s, data['plan'], token)
        if action == 'edit-plan':
            return service.edit_plan(s, data['plan'], data['hash'], data['edits'])
        if action == 'reject':
            return review.reject(s, data['plan'], data['hash'], data['rows'], data.get('reason', 'Not my preferred name'))
        if action == 'rollback-preview':
            value = transaction.rollback_preview(s, data['run'], data.get('folder'))
            key = uid()
            s.put('rollback-preview', key, value)
            return {'id': key, **value}
        if action == 'rollback':
            value = s.get('rollback-preview', data['preview'])
            if not value or value['conflicts']:
                raise ValueError('Preview rollback and resolve conflicts first')
            # The executor preflights again, catching edits made since preview.
            return transaction.undo(s, value['run'], value['folder'])
        if action == 'crawl-start':
            self.crawler.start(data['root'], data.get('speed', 'Background'))
            return {'status': 'starting'}
        if action == 'crawl-pause':
            s.put('background', 'paused', True)
            return self.crawler.pause()
        if action == 'background-resume':
            s.put('background', 'paused', False)
            # Let all chosen roots be checked again immediately.
            for root in gate.policy(s)['roots']:
                current = s.get('background-root', root, {})
                s.put('background-root', root, {**current, 'at': 0})
            return {'status': 'resumed'}
        if action == 'speed':
            return self.crawler.set_speed(data['speed'], data.get('idle_boost', False))
        if action == 'template-choice':
            files = service.scan(s, data['folder'], recursive=False)['files']
            return templates.teach(s, data['folder'], data['template'], files, data.get('teach', False))
        if action == 'confirm-rule':
            return templates.confirm(s, data['candidate'])
        if action == 'settings-preview':
            current = gate.policy(s)
            value = {**current, **data['settings']}
            if set(value) != set(gate.defaults()):
                raise ValueError('Unknown setting')
            if value['provider'] != 'off' or any(p != 'theophysics' for p in value['rulepacks']):
                raise ValueError('Only offline mode and listed rule packs are supported')
            preview = {'id': uid(), 'before_hash': digest(current), 'settings': value}
            s.put('settings-preview', preview['id'], preview)
            return preview
        if action == 'settings-save':
            preview = s.get('settings-preview', data['preview'])
            if not preview or preview['before_hash'] != digest(gate.policy(s)):
                raise ValueError('Settings changed; preview again')
            s.put('config', 'main', preview['settings'])
            return gate.policy(s)
        raise ValueError('Unknown action')


def make_server(store, port=43107):
    api = API(store)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def send(self, value, content_type='application/json', status=200):
            body = json.dumps(value).encode() if content_type == 'application/json' else value.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type+'; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.send({'error': 'Invalid host'}, status=403)
            url = urlsplit(self.path)
            q = parse_qs(url.query)
            try:
                if url.path == '/':
                    return self.send((STATIC/'index.html').read_text(encoding='utf-8').replace('FIS_TOKEN', token), 'text/html')
                if url.path in {'/app.js', '/live.js', '/style.css'}:
                    return self.send((STATIC/url.path[1:]).read_text(encoding='utf-8'), 'text/javascript' if url.path.endswith('.js') else 'text/css')
                if url.path == '/api/state':
                    return self.send(api.state())
                if url.path == '/api/progress':
                    progress = api.crawler.live_progress
                    crawl = api.crawler.live_status
                    return self.send({'progress': progress, 'server_time': time.time(),
                        'status': 'discovering' if progress.get('phase') == 'discovering' else crawl.get('status', 'idle'),
                        'files': crawl.get('files', 0), 'done': len(crawl.get('done', [])),
                        'remaining': len(crawl.get('remaining', [])),
                        'errors': len(crawl.get('errors', [])),
                        'waiting_templates': len(crawl.get('waiting_templates', []))})
                if url.path == '/api/health':
                    return self.send({'application': 'fis-standalone', 'state': str(store.home),
                                      'background': store.get('background', 'status', {})})
                if url.path == '/api/notifications':
                    state = api.state()
                    count = sum(p['pending_renames'] for p in state['plans'])
                    return self.send({'renames': count, 'templates': len(state['template_queue']),
                        'conflicts': len(state['conflicts']), 'errors': len(state['crawler'].get('errors', [])),
                        'crawler': state['crawler'].get('status'), 'background': state['background']})
                if url.path == '/api/preferences-export':
                    return self.send(preference.export(store), 'application/x-ndjson')
                if url.path == '/api/plan':
                    return self.send(store.get('plan', q['id'][0]))
                if url.path == '/api/search':
                    return self.send(store.search(q.get('q', [''])[0])[:500])
                if url.path == '/api/export':
                    fmt = q.get('format', ['html'])[0]
                    return self.send(export(store.get('plan', q['id'][0]), fmt), 'text/csv' if fmt == 'csv' else 'text/html')
                if url.path == '/api/folder-preview':
                    plan = store.get('plan', q['plan'][0])
                    row = next(r for r in plan['rows'] if r['id'] == q['row'][0] and r['kind']=='html')
                    return self.send(row['content'], 'text/html')
                return self.send({'error': 'Not found'}, status=404)
            except (KeyError, ValueError, OSError, StopIteration, TypeError) as error:
                return self.send({'error': str(error)}, status=400)

        def do_POST(self):
            origins = {f'http://localhost:{self.server.server_port}', f'http://127.0.0.1:{self.server.server_port}'}
            if (not self.valid_host() or self.headers.get('X-FIS-Token') != token or
                self.headers.get('Origin') not in origins or urlsplit(self.path).path != '/api/action'):
                return self.send({'error': 'Invalid local session'}, status=403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > 4_000_000:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                return self.send(api.action(data))
            except (KeyError, ValueError, OSError, RuntimeError, TypeError) as error:
                return self.send({'error': str(error)}, status=400)

    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self):
            if os.name == 'nt':
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = LocalServer(('127.0.0.1', port), Handler)
    server.api = api
    return server


def serve(store, port=43107):
    server = make_server(store, port)
    print(f'FIS is ready at http://127.0.0.1:{server.server_port}', flush=True)
    previous = server.api.crawler.status()
    if previous.get('status') in {'running', 'pausing'} and previous.get('root'):
        server.api.crawler.start(previous['root'], gate.policy(store)['speed'])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.api.crawler.pause()
    finally:
        server.server_close()
