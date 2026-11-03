import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from engine.topic_collection import plan_collection, collect_selection, review_html


class TopicCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        for rel, text in {'grace.md': 'Grace and restoration', '.trash/recovered.md': 'Charis and restoration',
                          'archive/old.md': 'Grace and restoration', 'unrelated.md': 'A different topic',
                          'node_modules/skip.md': 'Grace hidden in dependencies'}.items():
            path = self.source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        self.request = {'topic': 'grace', 'synonyms': ['charis'], 'roots': [str(self.source)], 'max_files': 100}

    def plan(self):
        return plan_collection(self.request, progress=lambda _: None)

    def test_trash_archive_and_exact_duplicate_tiers(self):
        result = self.plan()
        self.assertEqual({f['source_tier'] for f in result['files']}, {'active', 'archive', 'recovered_from_trash'})
        self.assertEqual(len(result['files']), 3)
        self.assertEqual(len(result['exact_duplicate_groups']), 1)
        self.request['include_trash'] = False
        self.assertEqual(len(self.plan()['files']), 2)

    def test_partial_scope_and_missing_seed_are_explicit(self):
        self.request.update(max_files=1, seeds=[{'name': 'not here', 'path_contains': ['missing-report']}])
        result = self.plan()
        self.assertTrue(result['partial'])
        self.assertEqual(result['seed_checks'][0]['status'], 'not_found_in_this_scope')

    def test_flat_verified_copies_keep_originals_and_all_versions(self):
        plan = self.plan()
        before = {str(p): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        selection = {'plan_sha256': plan['plan_sha256'], 'selected_paths': [f['path'] for f in plan['files']]}
        out = self.base / 'collection'
        result = collect_selection(plan, selection, out)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(result['exports']), 3)
        for row in result['exports']:
            self.assertEqual(hashlib.sha256((out / 'FILES' / row['exported_as']).read_bytes()).hexdigest(), row['sha256'])
            self.assertNotIn('/', row['exported_as'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.source.rglob('*') if p.is_file()})

    def test_source_change_and_wrong_selection_version_block_export(self):
        plan = self.plan()
        selection = {'plan_sha256': 'wrong', 'selected_paths': [plan['files'][0]['path']]}
        with self.assertRaises(ValueError):
            collect_selection(plan, selection, self.base / 'bad')
        selection['plan_sha256'] = plan['plan_sha256']
        Path(selection['selected_paths'][0]).write_text('Revised')
        with self.assertRaises(ValueError):
            collect_selection(plan, selection, self.base / 'changed')
        self.assertFalse((self.base / 'changed').exists())

    def test_same_named_different_drafts_both_copied(self):
        other = self.source / 'draft'
        other.mkdir()
        (other / 'grace.md').write_text('Grace in another draft')
        plan = self.plan()
        result = collect_selection(plan, {'plan_sha256': plan['plan_sha256'], 'selected_paths': [f['path'] for f in plan['files']]}, self.base / 'copies')
        names = [r['exported_as'] for r in result['exports']]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 4)

    def test_review_html_escapes_script_terminator(self):
        plan = self.plan()
        plan['topic'] = '</script><script>bad()</script>'
        rendered = review_html(plan)
        self.assertNotIn(plan['topic'], rendered)

    def test_explicit_file_formats_and_cancellation(self):
        (self.source / 'grace.html').write_text('<p>Grace</p>')
        self.request['extensions'] = ['.md']
        self.assertEqual({r['ext'] for r in self.plan()['files']}, {'.md'})
        stopped = plan_collection(self.request, stop=lambda: True, progress=lambda _: None)
        self.assertTrue(stopped['cancelled'])
        self.assertTrue(stopped['partial'])
        self.assertEqual(stopped['scanned_files'], 0)

    def test_file_type_layout_is_shallow(self):
        plan = self.plan()
        result = collect_selection(plan, {'plan_sha256': plan['plan_sha256'], 'selected_paths': [f['path'] for f in plan['files']]}, self.base / 'typed', layout='extension')
        self.assertEqual(result['layout'], 'extension')
        self.assertTrue(all(len(Path(row['exported_as']).parts) == 2 for row in result['exports']))

    def test_word_and_pdf_are_searched_by_body(self):
        from docx import Document
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        document = Document()
        document.add_paragraph('Charis is discussed in this document.')
        document.save(self.source / 'word-document.docx')
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(b'BT /F1 12 Tf 20 100 Td (Charis in this PDF) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(content)
        with (self.source / 'paper.pdf').open('wb') as stream:
            writer.write(stream)
        names = {Path(row['path']).name for row in self.plan()['files']}
        self.assertIn('word-document.docx', names)
        self.assertIn('paper.pdf', names)


if __name__ == '__main__':
    unittest.main()
