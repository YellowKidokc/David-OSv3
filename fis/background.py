"""Persistent scheduler for explicitly selected roots. No implicit drive scanning."""
import threading
import time
from pathlib import Path
from fis import gate, service, vocabulary
from fis.index import digest
from fis.scan import inventory


class Background:
    def __init__(self, api, interval=900):
        self.api, self.store = api, api.store
        self.interval = interval
        self.stop = threading.Event()
        self.thread = None

    def publish(self, **values):
        value = self.store.get('background', 'status', {})
        value.update({'enabled': True, 'heartbeat': time.time(), 'interval_seconds': self.interval, **values})
        self.store.put('background', 'status', value)

    def start(self):
        self.stop.clear()
        self.thread = threading.Thread(target=self.run, name='fis-background', daemon=True)
        self.thread.start()

    def run(self):
        self.publish(status='starting', started=time.time())
        while not self.stop.is_set():
            try:
                config = gate.policy(self.store)
                if self.store.get('background', 'paused', False):
                    self.publish(status='paused')
                elif not config['roots']:
                    self.publish(status='waiting-for-roots', message='Choose folders in Scan & Pick; no drives selected automatically')
                else:
                    for root in config['roots']:
                        if self.stop.is_set() or self.store.get('background', 'paused', False):
                            break
                        last = self.store.get('background-root', root, {})
                        if time.time()-last.get('at', 0) < self.interval:
                            continue
                        if self.api.crawler.running.is_set() or (self.api.crawler.thread and self.api.crawler.thread.is_alive()):
                            continue
                        self.publish(status='working', current=root)
                        try:
                            if not Path(root).is_dir():
                                raise OSError('Selected root is offline')
                            if any(gate.under(root, r) for r in config['html_roots']):
                                # Reuse one worker and checkpoint, so pause/resume affects scheduled work too.
                                self.api.crawler.stop_event.clear()
                                result = self.api.crawler.run(root, config['speed'])
                                signature = None
                                if result['errors']:
                                    raise RuntimeError(result['errors'][-1]['why'])
                            else:
                                result = inventory(root, config, on_file=self._pace_observation, vocab=vocabulary.layers(self.store.home))
                                if any(e.get('error') for e in result['skipped']):
                                    raise RuntimeError('Incomplete scan; unreadable paths need review')
                                signature = digest([(r['path'], r['sha256'], r['mtime_ns']) for r in result['files']])
                                if signature != last.get('signature'):
                                    # Plans only. Legacy notes remain untouched without explicit HTML policy.
                                    service.make_plan(self.store, root, html=False, scanned=result)
                            self.store.put('background-root', root, {'at': time.time(), 'signature': signature, 'error': None})
                        except InterruptedError:
                            self.publish(status='paused')
                        except Exception as error:
                            self.store.put('background-root', root, {'at': time.time(), 'error': str(error)})
                            self.publish(status='attention', error=str(error), current=root)
                    self.publish(status='waiting', current=None)
            except Exception as error:
                self.publish(status='attention', error=str(error))
            self.stop.wait(5)
        self.publish(status='stopped')

    def _pace_observation(self, row):
        from fis.crawler import PRESETS, thread_priority
        if self.store.get('background', 'paused', False) or self.stop.is_set():
            raise InterruptedError('Background work paused')
        preset = PRESETS[self.api.crawler.effective_speed()]
        thread_priority(preset['priority']=='background')
        self.publish(status='scanning', current_file=row['path'])
        self.stop.wait(60/preset['files_per_minute'] if preset['files_per_minute'] else 0)


def serve_background(store, port=43107, interval=900):
    from fis.web import make_server
    server = make_server(store, port)
    manager = Background(server.api, interval)
    server.api.background = manager
    with store.lock('service'):
        manager.start()
        print(f'FIS background service: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            manager.stop.set()
            server.api.crawler.pause()
            server.server_close()
