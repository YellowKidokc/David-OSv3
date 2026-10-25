"""Safety acceptance, not just implementation mirroring. Run with unittest or pytest."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fis import gate, service, transaction
from fis.index import Store


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(root).rglob('*') if p.is_file()}


class Foundation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base/'messy'
        self.root.mkdir()
        (self.root/'notes draft.txt').write_text('A method for observing evidence.\n', encoding='utf-8')
        (self.root/'copy.txt').write_bytes((self.root/'notes draft.txt').read_bytes())
        (self.root/'.fisnote').write_bytes(b'legacy\xff\x00 full content')
        self.store = Store(self.base/'state')
        service.configure_root(self.store, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self):
        return service.make_plan(self.store, self.root)

    def apply(self, plan, **kwargs):
        token = transaction.approve(self.store, plan['id'], plan['hash'])
        return transaction.apply(self.store, plan['id'], token, **kwargs)

    def test_offline_default_dry_run_and_exact_round_trip(self):
        before = snapshot(self.root)
        with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
            p = self.plan()
            self.assertEqual(snapshot(self.root), before)
            run = self.apply(p)
            self.assertNotEqual(snapshot(self.root), before)
            self.assertFalse((self.root/'.fisnote').exists())
            page = (self.root/'FIS.html').read_text(encoding='utf-8')
            self.assertIn('bGVnYWN5/wAgZnVsbCBjb250ZW50', page)
            result = transaction.undo(self.store, run['id'])
            self.assertFalse(result['conflicts'])
            self.assertEqual(snapshot(self.root), before)
            transaction.undo(self.store, run['id'])
            self.assertEqual(snapshot(self.root), before)
            self.assertTrue(list((self.store.home/'quarantine').rglob('FIS.html')))

    def test_exact_plan_approval_required_and_tamper_detected(self):
        p = self.plan()
        with self.assertRaises(PermissionError): transaction.apply(self.store, p['id'], 'absent')
        with self.assertRaises(ValueError): transaction.approve(self.store, p['id'], 'wrong-hash')
        token = transaction.approve(self.store, p['id'], p['hash'])
        p['rows'][0]['target'] = str(self.base/'escape.txt')
        self.store.put('plan', p['id'], p)
        with self.assertRaises(ValueError): transaction.apply(self.store, p['id'], token)

    def test_undo_refuses_later_edits_without_partial_restore(self):
        p = self.plan()
        run = self.apply(p)
        target = Path(next(r['target'] for r in p['rows'] if r['kind']=='rename'))
        target.write_text('later edit', encoding='utf-8')
        after = snapshot(self.root)
        self.assertTrue(transaction.undo(self.store, run['id'])['conflicts'])
        self.assertEqual(snapshot(self.root), after)

    def test_interrupted_run_is_recoverable(self):
        before = snapshot(self.root)
        p = self.plan()
        with self.assertRaises(RuntimeError): self.apply(p, fail_after=1)
        run = self.store.all('run')[0]
        self.assertFalse(transaction.undo(self.store, run['id'])['conflicts'])
        self.assertEqual(snapshot(self.root), before)

    def test_preexisting_html_restored_exactly(self):
        (self.root/'FIS.html').write_bytes(b'old page\r\n')
        before = snapshot(self.root)
        run = self.apply(self.plan())
        self.assertFalse(transaction.undo(self.store, run['id'])['conflicts'])
        self.assertEqual(snapshot(self.root), before)

    def test_partial_approval_and_source_hash_check(self):
        p = self.plan()
        row = next(r for r in p['rows'] if r['kind']=='rename')
        token = transaction.approve(self.store, p['id'], p['hash'], [row['id']])
        Path(row['path']).write_text('changed after scan')
        with self.assertRaises(ValueError): transaction.apply(self.store, p['id'], token)
        self.assertFalse((self.root/'FIS.html').exists())

    def test_duplicate_instances_preserved(self):
        s = service.scan(self.store, self.root)
        self.assertEqual(len(s['files']), 2)
        self.assertEqual(len({r['sha256'] for r in s['files']}), 1)
        self.assertEqual(len(self.store.search('method')), 2)

    def test_preview_and_blocked_floors_cannot_mutate(self):
        for floor in ['preview_only', 'blocked', 'suggest_only']:
            c = gate.policy(self.store)
            c['profiles'] = [{'root': str(self.root), 'approval_floor': floor}]
            self.store.put('config', 'main', c)
            p = self.plan()
            before = snapshot(self.root)
            with self.assertRaises(PermissionError): self.apply(p)
            self.assertEqual(snapshot(self.root), before)

    def test_protected_secret_and_bad_config_fail_closed(self):
        c = gate.policy(self.store)
        c['protected'] = [str(self.root)]
        self.store.put('config', 'main', c)
        with self.assertRaises(PermissionError): self.plan()
        self.store.put('config', 'main', {'roots': 'malformed'})
        with self.assertRaises(ValueError): service.scan(self.store, self.root)


class Independence(unittest.TestCase):
    def test_import_allowlist_and_no_delete_or_path_injection(self):
        package = Path(__file__).resolve().parents[1]/'fis'
        for path in package.glob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): names = [x.name for x in node.names]
                elif isinstance(node, ast.ImportFrom): names = [node.module or '']
                else: names = []
                for name in names:
                    self.assertIn(name.split('.')[0], sys.stdlib_module_names | {'fis', '__future__'}, (path, name))
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        self.assertNotIn(node.func.attr, {'unlink', 'remove', 'rmtree', 'import_module', 'spec_from_file_location'}, path)
                        if isinstance(node.func.value, ast.Name) and node.func.value.id in {'os', 'shutil'}:
                            self.assertNotEqual(node.func.attr, 'replace', path)
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, {'exec', 'eval', '__import__'}, path)
            self.assertNotIn('sys.path', path.read_text(encoding='utf-8'))

    def test_isolated_package_without_repo(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            shutil.copytree(repo/'fis', Path(td)/'fis', ignore=shutil.ignore_patterns('__pycache__'))
            result = subprocess.run([sys.executable, '-m', 'fis', '--help'], cwd=td, capture_output=True, text=True,
                                    env={k:v for k,v in os.environ.items() if k != 'PYTHONPATH'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('scan', result.stdout)


if __name__ == '__main__':
    unittest.main()
