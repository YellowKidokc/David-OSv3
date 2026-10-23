"""Start the existing authenticated Hub and open its private Sites interface."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://david-os-search.davidloweokc.chatgpt.site'
BASE = 'http://127.0.0.1:10000'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    state = ROOT / '.data'
    state.mkdir(exist_ok=True)
    token_file = state / 'search-site-token.txt'
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
    token = token_file.read_text(encoding='utf-8').strip()
    def healthy():
        try:
            req = urllib.request.Request(BASE + '/search/health', headers={'Authorization': 'Bearer ' + token})
            with urllib.request.urlopen(req, timeout=3) as response:
                return bool(json.load(response).get('rga'))
        except Exception:
            return False
    if not healthy():
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', 10000)) == 0:
                raise RuntimeError('Port 10000 is already in use. The existing service was left unchanged.')
        env = os.environ.copy()
        env['FIHUB_API_TOKEN'] = token
        env['FIHUB_SEARCH_ONLY'] = '1'
        env['FIHUB_ALLOWED_ORIGINS'] = SITE + ',http://127.0.0.1:10001'
        with (state / 'search-site-server.log').open('ab') as log:
            proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'hub.api.app:app', '--host', '127.0.0.1', '--port', '10000'], cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (state / 'search-site-server.pid').write_text(str(proc.pid), encoding='utf-8')
        for _ in range(30):
            if healthy():
                break
            time.sleep(1)
        else:
            raise RuntimeError('Hub did not become ready. See .data/search-site-server.log.')
    if not args.no_browser:
        # Fragments are processed in the browser and are not sent to Sites hosting.
        webbrowser.open(SITE + '#' + urllib.parse.urlencode({'localToken': token}))
    print('David OS search is ready on this computer.')

if __name__ == '__main__':
    main()
