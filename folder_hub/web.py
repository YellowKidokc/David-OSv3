from __future__ import annotations

import json
import re
import secrets
import threading
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from engine import registry
from folder_hub.service import FolderHub

STATIC = Path(__file__).parent/'static'


def style():
    # Reuse the existing FIS presentation rather than introducing a second theme.
    reference = registry.REPO/'gui/html/FIS.html'
    text = reference.read_text(encoding='utf-8') if reference.exists() else ''
    match = re.search(r'<style>(.*?)</style>',text,re.S|re.I)
    return (match.group(1) if match else 'body{background:#060708;color:#e7edf5;font:14px system-ui}') + '''
    .hub-header{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
    .hub-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
    .hub-card,.assistant{border:1px solid #222a35;background:#0c0f14;padding:16px;margin:12px 0}
    textarea{width:100%;min-height:90px;background:#090b0f;color:#e7edf5;border:1px solid #334052;padding:12px;font:inherit}
    .answer{white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0;max-height:450px;overflow:auto}
    .status{color:#d1a922}.error{color:#ffb9a4}.source{color:#8b97a7;font:11px Consolas,monospace;overflow-wrap:anywhere}
    .hub-row{display:grid;grid-template-columns:25px minmax(180px,1fr) auto;gap:12px;padding:12px;border-bottom:1px solid #222a35}
    button:disabled{opacity:.5;cursor:wait}.missing{opacity:.65}.assistant small{display:block;color:#8b97a7}
    .hub-form{display:flex;gap:8px;flex-wrap:wrap}.hub-form input,.hub-form select{background:#090b0f;color:#e7edf5;border:1px solid #334052;padding:8px}
    dialog{background:#0c0f14;color:#e7edf5;max-width:900px;width:90%;border:1px solid #d1a922}dialog pre{white-space:pre-wrap;max-height:65vh;overflow:auto}
    @media(max-width:800px){.hub-row{grid-template-columns:25px 1fr}.hub-row button{grid-column:2}.layout{display:block}}
    '''


def page(service, identity=None, relative='.'):
    hub = service.hub(identity) if identity else None
    view = service.view(identity,relative) if hub else None
    title = (hub['label'] if view['relative']=='.' else Path(view['path']).name) if hub else 'FIS Folder Hubs'
    data = {'hub': hub, 'view':view, 'files': view['files'] if hub else [], 'state': service.state()}
    embedded = json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="fis-session" content="FIS_SESSION_PLACEHOLDER"><title>FIS | '''+escape(title)+'''</title><style>'''+style()+'''</style></head>
    <body><div class="layout"><aside class="sidebar"><div class="side-title">FIS · Folder intelligence</div><a href="./">All hubs</a>
    <div class="side-label">Your scopes</div><div id="hub-nav"></div><div class="side-label">Central relay</div><div id="relay-status" class="muted"></div></aside>
    <main><div class="eyebrow">DAVID-OS / FIS FOLDER TASK</div><div class="hub-header"><h1>'''+escape(title)+'''</h1><span id="connection" class="status">Connecting…</span></div>
    <p class="muted">Folder observations, document context, and questions in one place.</p>
    <div id="message" role="status" aria-live="polite"></div><div id="overview"></div>
    <section id="folder-controls" hidden><button id="check">Check for changes</button> <button id="refresh">Refresh folder view</button>
    <button id="pause">Pause hub</button>
    <p id="checked" class="muted"></p><div id="changes"></div>
    <h2>Child folders</h2><div id="subfolders"></div>
    <h2>Files here</h2><input id="filter" type="search" aria-label="Find a file" placeholder="Find by name, title, or path"><div id="files"></div>
    <section class="assistant"><h2>Ask this folder</h2><small id="ai-status"></small>
    <p class="muted">Select up to three files to include their text. Without a selection, the assistant receives the scoped inventory and latest check.</p>
    <textarea id="question" aria-label="Question for this folder" placeholder="What changed? Which documents should I open?"></textarea>
    <button id="ask">Ask DeepSeek</button><div id="answer" class="answer" aria-live="polite"></div></section></section>
    <section id="add-section" hidden><h2>Add a folder hub</h2><p class="muted">Choose the exact folder or drive scope to monitor. Large folders can have their own hub.</p>
    <form id="add-hub" class="hub-form"><input name="label" aria-label="Hub name" placeholder="Desktop / Documents / Drive D" required>
    <input name="root" aria-label="Folder path" placeholder="Full folder path" required><select name="kind" aria-label="Hub kind"><option value="folder">Folder</option><option value="drive">Drive</option></select>
    <button>Add hub</button></form></section><h2>Recent commands</h2><div id="commands"></div>
    <p class="muted">Source files remain in place. Missing paths, proposed classifications, and human rulings remain distinct.</p></main></div>
    <dialog id="source-dialog"><button id="close-source">Close</button><h2 id="source-title"></h2><p id="source-note" class="muted"></p><pre id="source-body"></pre></dialog>
    <script id="fis-folder-record" type="application/json">'''+embedded+'''</script><script src="static/app.js"></script></body></html>'''


def folder_page(service, identity):
    return page(service,identity)


def create_app(home, *, scheduled=False, allowed_hosts=('127.0.0.1','localhost')):
    service = FolderHub(home)
    token = secrets.token_urlsafe(32)
    stop = threading.Event()
    @asynccontextmanager
    async def lifespan(app):
        worker = None
        if scheduled:
            worker = threading.Thread(target=service.watch,args=(stop,),daemon=True,name='fis-hub-checks')
            worker.start()
        yield
        stop.set()
        if worker:
            worker.join(timeout=2)
    app = FastAPI(title='FIS Folder Hubs',lifespan=lifespan)
    app.state.service, app.state.token = service, token

    @app.middleware('http')
    async def local_session(request: Request, call_next):
        host = request.headers.get('host','')
        if urlsplit('http://'+host).hostname not in allowed_hosts:
            return JSONResponse({'detail':'Invalid local host'},status_code=403)
        if request.method != 'GET':
            origin = request.headers.get('origin','')
            if request.headers.get('x-fis-token') != token or origin not in {'http://'+host,'https://'+host}:
                return JSONResponse({'detail':'Invalid local session'},status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.get('/',response_class=HTMLResponse)
    def dashboard():
        return page(service).replace('FIS_SESSION_PLACEHOLDER',token)

    @app.get('/folder',response_class=HTMLResponse)
    def folder(id: str, relative: str='.'):
        try:
            return page(service,id,relative).replace('FIS_SESSION_PLACEHOLDER',token)
        except ValueError as exc:
            raise HTTPException(404,str(exc))

    @app.get('/static/app.js')
    def script():
        return FileResponse(STATIC/'app.js',media_type='text/javascript')

    @app.get('/api/state')
    def state():
        return service.state()

    @app.get('/api/files')
    def files(hub: str):
        try:
            return service.records(hub)
        except ValueError as exc:
            raise HTTPException(404,str(exc))

    @app.get('/api/view')
    def view(hub: str, relative: str='.'):
        try:
            return service.view(hub,relative)
        except (ValueError,OSError) as exc:
            raise HTTPException(400,str(exc))

    @app.post('/api/commands')
    def command(body: dict):
        try:
            payload = dict(body)
            identity, action = payload.pop('hub'),payload.pop('action')
            return service.command(action,identity,**payload)
        except (KeyError,ValueError) as exc:
            raise HTTPException(400,str(exc))

    @app.post('/api/hubs')
    def add_hub(body: dict):
        try:
            with service.lock:
                return service.add_hub(body['root'],body['label'],kind=body.get('kind','folder'))
        except (KeyError,ValueError,OSError) as exc:
            raise HTTPException(400,str(exc))
    return app
