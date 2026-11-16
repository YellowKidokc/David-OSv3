"""Timed desktop pass with the existing FIS worker and local River monitor."""
from shared.runtime_config import path_setting as _portable_path
from pathlib import Path as _PortablePath
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fis.index import Store
from fis import service
from fis.web import make_server

if __name__ == '__main__':
    root = Path(str(_portable_path('DAVID_OS_LEGACY_DESKTOP_LIVE_DESKTOP', 'legacy_desktop_live_desktop', _PortablePath(__file__).resolve().parents[2] / '_local/Desktop')))
    store = Store(root.parent/'_FIS_DESKTOP_STATE')
    service.configure_root(store, root, html=True)
    server = make_server(store, 43108)
    def run():
        start = time.monotonic()
        try:
            result = server.api.crawler.run(str(root), 'Full')
            summary = {'elapsed_seconds': round(time.monotonic()-start, 2),
                       'result': result}
        except Exception as error:
            server.api.crawler.activity('worker error', str(root), force=True, error=str(error))
            summary = {'elapsed_seconds': round(time.monotonic()-start, 2), 'error': str(error)}
        (store.home/'desktop-pass-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    threading.Thread(target=run, daemon=True).start()
    print('River monitor http://127.0.0.1:43108', flush=True)
    server.serve_forever()
