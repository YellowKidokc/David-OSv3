"""Checkpointed folder worker. Only authorized HTML rows can auto-apply."""
import ctypes
import os
import threading
import time
from pathlib import Path
from fis import gate, service, templates, transaction
from fis.index import uid
from fis.index import digest
from fis.fingerprint import sha256_file

PRESETS = {'Trickle': {'files_per_minute': 6, 'folder_pause': 10, 'priority': 'background'},
           'Background': {'files_per_minute': 60, 'folder_pause': 2, 'priority': 'background'},
           'Normal': {'files_per_minute': 300, 'folder_pause': .2, 'priority': 'normal'},
           'Full': {'files_per_minute': 0, 'folder_pause': 0, 'priority': 'normal'}}


def idle_seconds():
    if os.name != 'nt':
        return None  # unsupported platforms show unavailable; never assume idle
    class LastInput(ctypes.Structure):
        _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]
    value = LastInput()
    value.cbSize = ctypes.sizeof(value)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(value)):
        return None
    return ((ctypes.windll.kernel32.GetTickCount() - value.dwTime) & 0xffffffff)/1000


def thread_priority(background):
    if os.name == 'nt':
        # Windows thread background mode lowers scheduling and I/O priority together.
        ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(),
                                               0x10000 if background else 0x20000)


class Crawler:
    def __init__(self, store, wait=None):
        self.store = store
        self.stop_event = threading.Event()
        self.wait = wait or self.stop_event.wait
        self.thread = None
        self.running = threading.Event()
        self._last_activity = 0
        self._activity = []
        self.live_progress = {}
        self.live_status = {}

    def activity(self, phase, path='', force=False, **counts):
        now = time.time()
        self._activity.append({'at': now, 'phase': phase, 'path': str(path)})
        self._activity = self._activity[-40:]
        self.live_progress = {'phase': phase, 'path': str(path), 'updated': now,
                              'events': list(self._activity), **counts}
        if force or now - self._last_activity >= 1.5:
            self.store.put('progress', 'live', self.live_progress)
            self._last_activity = now

    def status(self):
        return self.store.get('crawler', 'status', {'status': 'stopped', 'done': [], 'remaining': [], 'errors': [], 'files': 0})

    def save(self, value):
        self.live_status = dict(value)
        self.store.put('crawler', 'status', value)

    def start(self, root, speed='Background'):
        if self.running.is_set() or (self.thread and self.thread.is_alive()):
            raise ValueError('Crawler is already running')
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._background, args=(root, speed), daemon=True)
        self.thread.start()

    def _background(self, root, speed):
        try:
            self.run(root, speed)
        except Exception as error:
            s = self.status()
            s['status'] = 'error'
            s.setdefault('errors', []).append({'folder': str(root), 'why': str(error)})
            self.save(s)

    def pause(self):
        self.stop_event.set()
        s = self.status()
        s['status'] = 'pausing' if self.thread and self.thread.is_alive() else 'paused'
        self.save(s)
        return s

    def set_speed(self, speed, idle_boost=False):
        if speed not in PRESETS:
            raise ValueError('Unknown speed preset')
        c = gate.policy(self.store)
        c['speed'], c['idle_boost'] = speed, bool(idle_boost)
        self.store.put('config', 'main', c)
        return c

    def effective_speed(self):
        c = gate.policy(self.store)
        idle = idle_seconds() if c['idle_boost'] else None
        return 'Full' if idle is not None and idle >= 300 else c['speed']

    def paced_file(self, row):
        preset = PRESETS[self.effective_speed()]
        thread_priority(preset['priority'] == 'background')
        s = self.status()
        s['files'] += 1
        s['current_file'] = row['path']
        s['effective_speed'] = self.effective_speed()
        elapsed = max(time.time()-s['started'], .01)
        s['files_per_minute'] = round(s['files']*60/elapsed, 1)
        self.save(s)
        self.activity('classified', row['path'], files=s['files'])
        delay = 60/preset['files_per_minute'] if preset['files_per_minute'] else 0
        if self.wait(delay):
            raise InterruptedError('Paused between files; folder will resume safely')

    def run(self, root, speed='Background', max_folders=None):
        with self.store.lock('crawler'):
            self.running.set()
            try:
                return self._run(root, speed, max_folders)
            finally:
                self.running.clear()
                thread_priority(False)

    def _run(self, root, speed, max_folders):
        root = str(Path(root).resolve())
        c = gate.check(self.store, root, [root], 'move')
        if not any(gate.under(root, x) for x in c['html_roots']):
            raise PermissionError('Enable HTML automation for this root after reviewing its preview')
        self.set_speed(speed, c['idle_boost'])
        # Separate process mutex prevents two crawlers sharing a checkpoint.
        s = self.status()
        if s.get('root') != root or s.get('status') == 'complete':
            folders = []
            self.activity('discovering', root, force=True, folders_discovered=0)
            for here, dirs, _ in os.walk(root, followlinks=False):
                if self.stop_event.is_set():
                    self.activity('paused', here, force=True)
                    return self.status()
                self.activity('discovering', here, folders_discovered=len(folders)+1)
                dirs[:] = sorted(d for d in dirs if not gate.unsafe(Path(here)/d, c))
                folders.append(here)
            s = {'id': uid(), 'root': root, 'done': [], 'remaining': sorted(folders), 'errors': [],
                 'status': 'running', 'files': 0, 'started': time.time(), 'current': None,
                 'plans': {}, 'runs': {}, 'waiting_templates': []}
        s['status'] = 'running'
        self.save(s)
        completed = 0
        for folder in list(s['remaining']):
            if self.stop_event.is_set():
                break
            try:
                s = self.status()
                s['current'] = folder
                self.save(s)
                gate.check(self.store, root, [folder], 'move')
                prior = s['plans'].get(folder)
                if prior:
                    runs = [r for r in self.store.all('run') if r['plan'] == prior]
                    if runs and runs[0]['status'] == 'applied':
                        s['runs'][folder] = runs[0]['id']
                        s['done'].append(folder)
                        s['remaining'].remove(folder)
                        self.save(s)
                        continue
                    if runs and runs[0]['status'] in {'applying', 'interrupted'}:
                        restored = transaction.undo(self.store, runs[0]['id'])
                        if restored['conflicts']:
                            raise ValueError('Interrupted folder has rollback conflicts; review before retry')
                self.activity('scanning folder', folder, force=True)
                result = service.scan(self.store, folder, recursive=False, on_file=self.paced_file,
                                      on_stage=self.activity)
                selection = templates.choose(self.store, folder, result['files'])
                if selection['template'] is None:
                    self.activity('needs template choice', folder, force=True)
                    self.store.put('template-queue', folder, {'folder': folder, 'choice': selection})
                    s = self.status()
                    if folder not in s['waiting_templates']:
                        s['waiting_templates'].append(folder)
                    self.save(s)
                    continue
                signature = digest({'files': [(r['path'], r['sha256'], r['mtime_ns']) for r in result['files']],
                                    'template': selection['template'], 'packs': gate.policy(self.store)['rulepacks']})
                checkpoint = self.store.get('folder-checkpoint', folder)
                page = Path(folder)/'FIS.html'
                if (checkpoint and checkpoint['signature'] == signature and page.is_file()
                    and sha256_file(page) == checkpoint['html_hash']
                    and not list(Path(folder).glob('*.fisnote'))
                    and self.store.get('run', checkpoint['run'], {}).get('status') == 'applied'):
                    s = self.status()
                    s['done'].append(folder)
                    s['remaining'].remove(folder)
                    self.save(s)
                    continue
                plan = service.make_plan(self.store, folder, recursive=False, template=selection['template'], scanned=result)
                self.activity('writing HTML', folder, force=True)
                s = self.status()
                s['plans'][folder] = plan['id']
                self.save(s)
                # Only HTML is approved under the root's explicit automation policy.
                html_ids = [r['id'] for r in plan['rows'] if r['kind']=='html']
                token = transaction.approve(self.store, plan['id'], plan['hash'], html_ids, automatic=True)
                run = transaction.apply(self.store, plan['id'], token)
                self.store.put('folder-checkpoint', folder, {'signature': signature,
                    'html_hash': sha256_file(Path(folder)/'FIS.html'), 'run': run['id'], 'plan': plan['id']})
                s = self.status()
                s['runs'][folder] = run['id']
                s['done'].append(folder)
                s['remaining'].remove(folder)
                s['waiting_templates'] = [f for f in s['waiting_templates'] if f != folder]
                self.store.put('template-queue', folder, {'folder': folder, 'resolved': True, 'choice': selection})
                score = max(0, 100-10*len(plan['skipped'])-5*sum(bool(r['flag']) for r in plan['rows']))
                self.store.put('health', uid(), {'folder': folder, 'at': time.time(), 'score': score,
                    'why': 'Operational inventory completeness and held proposals; not scientific or theological validity'})
                self.save(s)
                completed += 1
                if max_folders and completed >= max_folders:
                    break
                if self.wait(PRESETS[self.effective_speed()]['folder_pause']):
                    break
            except InterruptedError:
                break
            except Exception as error:
                self.activity('folder error', folder, force=True, error=str(error))
                s = self.status()
                s['errors'].append({'folder': folder, 'why': str(error), 'at': time.time()})
                self.save(s)
        s = self.status()
        s['status'] = 'complete' if not s['remaining'] else ('paused' if self.stop_event.is_set() or max_folders else 'waiting')
        s['current'] = None
        self.save(s)
        self.activity(s['status'], root, force=True, files=s['files'],
                      folders_done=len(s['done']), errors=len(s['errors']))
        thread_priority(False)
        return s
