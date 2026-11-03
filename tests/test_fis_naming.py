"""Naming behaviour: series widths, dotted IDs, CamelCase, learned tier, laws registry and holds."""
import json
import time
import unittest
from pathlib import Path

from fis.rename import propose

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / 'docs' / 'vocabulary-candidates'


def load(name):
    return json.loads((CANDIDATES / name).read_text(encoding='utf-8'))


def stem(result):
    return result['name'].rsplit('__', 2)[0]


class Core(unittest.TestCase):
    def test_leading_zeros_and_dotted_ids_survive(self):
        r = propose('012_EQUATION_E2.1_Master-Equation-First-Form.md', '', time.time(), ('theophysics',))
        self.assertIn('__012_equation_e2_1_master_equation', r['name'])
        r = propose('146_EQUATION_E19.1_Full-Master-Equation.md', '', time.time())
        self.assertIn('146_equation_e19_1_', r['name'])

    def test_single_digit_series_is_padded(self):
        self.assertIn('__01_intro__', propose('1_intro.md', '', time.time())['name'])

    def test_camel_case_is_split_and_matched(self):
        r = propose('MasterEquationSpiritualIsomorphism.lean', '', time.time(), ('theophysics',))
        self.assertTrue(r['name'].startswith('MEQ__'))
        self.assertIn('master_equation_spiritual_isomorphism', r['name'])


class Learned(unittest.TestCase):
    def setUp(self):
        self.learned = load('vocabulary.user.draft.json')

    def test_learned_rules_follow_core_and_are_labelled(self):
        r = propose('081_EQUATION_E9.1_Grace-Function.md', '', time.time(), ('theophysics',), self.learned)
        self.assertEqual(r['name'].split('__')[:2], ['GRC', 'EQN'])
        self.assertTrue(any('[new class, provisional]' in w['evidence'] for w in r['why']))

    def test_core_wins_a_tie(self):
        core = propose('master_equation_notes.md', '', time.time(), ('theophysics',))
        with_learned = propose('master_equation_notes.md', '', time.time(), ('theophysics',), self.learned)
        self.assertEqual(core['name'].split('__')[0], with_learned['name'].split('__')[0])

    def test_rejected_rules_are_ignored(self):
        learned = json.loads(json.dumps(self.learned))
        for rule in learned['types']:
            if rule['code'] == 'EQN':
                rule['provenance']['state'] = 'rejected'
        r = propose('081_EQUATION_E9.1_Grace-Function.md', '', time.time(), ('theophysics',), learned)
        self.assertNotEqual(r['name'].split('__')[1], 'EQN')

    def test_extension_types(self):
        r = propose('Foo.lean', '', time.time(), (), self.learned)
        self.assertEqual(r['name'].split('__')[1], 'LEA')


class Laws(unittest.TestCase):
    def setUp(self):
        self.learned = load('vocabulary.user.draft.json')
        self.laws = load('laws.registry.draft.json')

    def propose(self, name):
        return propose(name, '', time.time(), ('theophysics',), self.learned, self.laws)

    def test_law_files_share_a_domain_and_use_registry_names(self):
        r = self.propose('LAW_03_MAXWELL_TRUTH.md')
        self.assertEqual(stem(r), 'LAW__CRD__l03_maxwell_truth')
        self.assertNotIn('hold', r)

    def test_expansion_documents_get_their_own_type(self):
        r = self.propose('LAW_01_GRAVITY_GRACE_EXPANSION.md')
        self.assertEqual(r['name'].split('__')[:2], ['LAW', 'EXP'])

    def test_number_conflict_is_held_not_renamed_to_a_guess(self):
        for name in ('LAW_08_FERMI_CONSERVATION.md', 'LAW_09_EINSTEIN_FRAME.md'):
            r = self.propose(name)
            self.assertIn('hold', r, name)
            self.assertEqual(r['confidence'], 0.3)
            self.assertIn('law_0', r['name'])    # keeps the file's own number

    def test_without_a_registry_law_files_still_share_a_domain(self):
        r = propose('LAW_05_CLAUSIUS_JUDGMENT.md', '', time.time(), ('theophysics',), self.learned)
        self.assertEqual(r['name'].split('__')[0], 'LAW')


if __name__ == '__main__':
    unittest.main()
