"""Learned vocabulary tier, suggestion counter, and scan integration."""
import json
import tempfile
import unittest
from pathlib import Path

from fis import service, vocabulary
from fis.index import Store


def fake_files(term, count, folders=3, domain='GEN', typ='ART'):
    rows = []
    for i in range(count):
        folder = 'C:/src/f%d' % (i % folders)
        rows.append({'id': '%s-%d' % (term, i), 'folder': folder,
                     'rename': {'name': '%s__%s__%s_notes_%d__20261025__AC.md' % (domain, typ, term, i)}})
    return {'files': rows}


class Layers(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def test_shipped_vocabulary_and_registry_load_and_validate(self):
        got = vocabulary.layers(self.home)
        self.assertEqual(got['warnings'], [])
        codes = {r['code'] for r in got['learned']['types']}
        self.assertTrue({'EQN', 'LEA', 'CRD', 'EXP'} <= codes)
        self.assertEqual(len(got['laws']['laws']), 10)

    def test_invalid_user_file_is_ignored_with_a_warning(self):
        (self.home / vocabulary.USER).write_text(json.dumps({'domains': [{'code': 'toolong', 'words': ['x']}]}), encoding='utf-8')
        got = vocabulary.layers(self.home)
        self.assertTrue(any('ignored' in w for w in got['warnings']))
        self.assertIsNotNone(got['learned'])      # shipped tier still works

    def test_writer_refuses_invalid_vocabulary(self):
        with self.assertRaises(ValueError):
            vocabulary._write(self.home / 'x.json', {'domains': [{'code': 'a', 'words': ['zz']}]})


class Counter(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def test_below_threshold_creates_nothing(self):
        self.assertEqual(vocabulary.observe(self.home, fake_files('tarot', 10)), [])

    def test_promotes_past_threshold_with_a_unique_provisional_code(self):
        created = vocabulary.observe(self.home, fake_files('tarot', 15))
        domains = [c for c in created if c['table'] == 'domains']
        self.assertEqual(len(domains), 1)
        code = domains[0]['code']
        self.assertRegex(code, r'^[A-Z]{3}$')
        self.assertNotIn(code, vocabulary._core_codes())
        user = json.loads((self.home / vocabulary.USER).read_text(encoding='utf-8'))
        self.assertEqual(user['domains'][0]['provenance']['state'], 'provisional')

    def test_needs_several_folders_not_just_many_files(self):
        self.assertEqual(vocabulary.observe(self.home, fake_files('tarot', 30, folders=1)), [])

    def test_known_words_are_not_proposed_again(self):
        self.assertEqual(vocabulary.observe(self.home, fake_files('physics', 20)), [])

    def test_counts_accumulate_across_scans(self):
        vocabulary.observe(self.home, fake_files('tarot', 8))
        self.assertEqual(vocabulary.observe(self.home, fake_files('tarot', 8)), [])   # same ids: still 8 distinct
        more = fake_files('tarot', 20)
        self.assertTrue(vocabulary.observe(self.home, more))

    def test_rejected_codes_are_not_used_by_propose(self):
        created = vocabulary.observe(self.home, fake_files('tarot', 15))
        code = [c for c in created if c['table'] == 'domains'][0]['code']
        vocabulary.reject(self.home, code)
        learned = vocabulary.layers(self.home)['learned']
        from fis.rename import propose
        import time
        r = propose('tarot_spread.md', '', time.time(), (), learned)
        self.assertNotEqual(r['name'].split('__')[0], code)

    def test_confirm_marks_state_and_status_lists_pending(self):
        created = vocabulary.observe(self.home, fake_files('tarot', 15))
        code = [c for c in created if c['table'] == 'domains'][0]['code']
        self.assertIn(code, [p['code'] for p in vocabulary.status(self.home)['provisional']])
        vocabulary.confirm(self.home, code)
        self.assertNotIn(code, [p['code'] for p in vocabulary.status(self.home)['provisional']])

    def test_derive_code_avoids_collisions(self):
        taken = {'TAR'}
        self.assertNotIn(vocabulary.derive_code('tarot', taken), taken)


class ScanIntegration(unittest.TestCase):
    def test_scan_uses_the_registry_and_learned_types(self):
        src, state = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (src / 'LAW_03_MAXWELL_TRUTH.md').write_text('# Law three\ntruth\n', encoding='utf-8')
        (src / 'LAW_08_FERMI_CONSERVATION.md').write_text('# Law eight\n', encoding='utf-8')
        (src / 'Proof.lean').write_text('theorem x : True := trivial\n', encoding='utf-8')
        result = service.scan(Store(state), str(src))
        names = {Path(r['path']).name: r['rename'] for r in result['files']}
        self.assertTrue(names['LAW_03_MAXWELL_TRUTH.md']['name'].startswith('LAW__CRD__l03_maxwell_truth__'))
        self.assertIn('hold', names['LAW_08_FERMI_CONSERVATION.md'])
        self.assertEqual(names['Proof.lean']['name'].split('__')[1], 'LEA')

    def test_held_rename_cannot_be_applied_by_default(self):
        src, state = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        (src / 'LAW_08_FERMI_CONSERVATION.md').write_text('# Law eight\n', encoding='utf-8')
        plan = service.make_plan(Store(state), str(src), html=False)
        row = next(r for r in plan['rows'] if r['kind'] == 'rename')
        self.assertTrue(row['flag'].startswith('law-number'))


if __name__ == '__main__':
    unittest.main()
