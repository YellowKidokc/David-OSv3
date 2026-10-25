"""Always-on, human-in-the-loop, and preference-learning acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from fis import gate, preference, review, service, transaction
from fis.background import Background
from fis.crawler import Crawler
from fis.index import Store
from fis.web import API


class Runtime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base/'documents'
        self.root.mkdir()
        (self.root/'notes draft.txt').write_text('A method for testing observations')
        self.store = Store(self.base/'state')
        service.configure_root(self.store, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_rejection_is_durable_idempotent_and_trains_existing_engines(self):
        p = service.make_plan(self.store, self.root)
        row = next(r for r in p['rows'] if r['kind']=='rename')
        review.reject(self.store, p['id'], p['hash'], [row['id']])
        review.reject(self.store, p['id'], p['hash'], [row['id']])
        self.assertEqual(preference.stats(self.store)['decisions'], 1)
        self.assertEqual(review.summaries(self.store)[0]['pending_renames'], 0)
        self.assertTrue(Path(row['path']).exists())
        self.assertEqual(preference.stats(Store(self.store.home))['rejected'], 1)

    def test_correction_requires_new_approval_and_learns_original_and_replacement(self):
        p = service.make_plan(self.store, self.root)
        row = next(r for r in p['rows'] if r['kind']=='rename')
        token = transaction.approve(self.store, p['id'], p['hash'], [row['id']])
        corrected = service.edit_plan(self.store, p['id'], p['hash'], {row['id']: 'My preferred title.txt'})
        self.assertNotEqual(p['hash'], corrected['hash'])
        self.assertIn('My preferred title.txt', next(r['content'] for r in corrected['rows'] if r['kind']=='html'))
        with self.assertRaises(PermissionError): transaction.apply(self.store, corrected['id'], token)
        token = transaction.approve(self.store, corrected['id'], corrected['hash'], [row['id']])
        run = transaction.apply(self.store, corrected['id'], token)
        self.assertTrue((self.root/'My preferred title.txt').exists())
        self.assertEqual(preference.stats(self.store)['approved'], 1)
        self.assertEqual(preference.stats(self.store)['rejected'], 1)
        self.assertFalse(transaction.undo(self.store, run['id'])['conflicts'])

    def test_crawler_html_apply_keeps_rename_queue_and_never_trains_auto_approval(self):
        service.configure_root(self.store, self.root, html=True)
        c = Crawler(self.store, wait=lambda _:False)
        c.run(self.root, 'Full')
        summary = review.summaries(self.store)[0]
        self.assertEqual(summary['pending_renames'], 1)
        self.assertFalse(summary['applied'])
        self.assertEqual(preference.stats(self.store)['decisions'], 0)
        self.assertTrue((self.root/'notes draft.txt').exists())
        c.run(self.root, 'Full')
        self.assertEqual(len(self.store.all('run')), 1)  # unchanged folders do not churn HTML/archives

    def test_preference_warmup_scores_but_never_approves(self):
        p = service.make_plan(self.store, self.root)
        row = next(r for r in p['rows'] if r['kind']=='rename')
        for i in range(12):
            preference.record(self.store, {**p, 'hash': str(i), 'id': str(i)}, row, True)
        q = service.make_plan(self.store, self.root)
        learned = next(r for r in q['rows'] if r['kind']=='rename')['preference']
        self.assertTrue(learned['ready'])
        self.assertGreater(learned['score'], .5)
        self.assertFalse(learned['auto_approval'])
        with self.assertRaises(PermissionError): transaction.apply(self.store, q['id'], 'none')

    def test_no_root_background_waits_without_scanning_drives(self):
        self.store.put('config', 'main', gate.defaults())
        worker = Background(API(self.store), interval=30)
        worker.start()
        end = time.time()+5
        while time.time()<end and self.store.get('background', 'status', {}).get('status')!='waiting-for-roots':
            time.sleep(.02)
        self.assertEqual(self.store.get('background', 'status')['status'], 'waiting-for-roots')
        worker.stop.set()
        worker.thread.join(5)
        self.assertFalse(self.store.all('plan'))

    def test_actual_process_exit_mid_apply_recovers_from_intent(self):
        p = service.make_plan(self.store, self.root)
        row = next(r for r in p['rows'] if r['kind']=='rename')
        token = transaction.approve(self.store, p['id'], p['hash'], [row['id']])
        code = '''import os,sys
from fis.index import Store
from fis import transaction
original=transaction._move
def interrupted(src,dst):
 original(src,dst)
 os._exit(17)
transaction._move=interrupted
transaction.apply(Store(sys.argv[1]),sys.argv[2],sys.argv[3])
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.store.home), p['id'], token])
        self.assertEqual(result.returncode, 17)
        run = self.store.all('run')[0]
        self.assertEqual(run['status'], 'applying')
        self.assertFalse(transaction.undo(self.store, run['id'])['conflicts'])
        self.assertTrue(Path(row['path']).exists())

    def test_rust_symptoms_and_secrets_excluded_before_extraction(self):
        (self.root/'Cargo.toml').write_text('[package]')
        (self.root/'paper_v2.txt').write_text('same')
        (self.root/'paper_copy.txt').write_text('same')
        (self.root/'.env.local').write_text('SHOULD NOT BE READ')
        s = service.scan(self.store, self.root)
        self.assertTrue({'I01', 'I03', 'C01', 'S02'} <= {r['id'] for r in s['symptoms']})
        self.assertNotIn('.env.local', [Path(r['path']).name for r in s['files']])

    def test_local_service_refuses_second_listener_on_same_port(self):
        from fis.web import make_server
        server = make_server(self.store, 0)
        try:
            with self.assertRaises(OSError):
                make_server(self.store, server.server_port)
        finally:
            server.server_close()


if __name__ == '__main__':
    unittest.main()
