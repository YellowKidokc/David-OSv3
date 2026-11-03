"""Native GUI state/worker checks with temporary sources and outputs only."""
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path

from engine.topic_collection import plan_collection

FILE = Path(__file__).resolve().parents[1] / '05_TOPIC_COLLECTION/BACKSIDE/topic_gui.py'
spec = importlib.util.spec_from_file_location('topic_collection_gui', FILE)
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)


class TopicGUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.old_station = gui.STATION
        gui.STATION = self.base / 'station'
        (gui.STATION / 'OUTBOX').mkdir(parents=True)
        self.addCleanup(setattr, gui, 'STATION', self.old_station)
        self.source = self.base / 'source'
        nested = self.source.joinpath(*['folder' + str(i) for i in range(15)])
        nested.mkdir(parents=True)
        (nested / 'grace.md').write_text('Grace and restoration')
        (self.source / 'grace.txt').write_text('Charis and restoration')
        self.plan = plan_collection({'topic': 'grace', 'roots': [str(self.source)], 'synonyms': ['charis'],
                                     'extensions': ['.md', '.txt']}, progress=lambda _: None)
        self.app = gui.TopicCollectionGUI()
        self.app.withdraw()
        self.addCleanup(self.app.destroy)
        self.app.load_plan(self.plan, self.base)
        self.app.update()

    def test_deep_sources_become_flat_rows_with_hierarchy_retained(self):
        self.assertEqual(len(self.app.table.get_children()), 2)
        self.assertIn('15', self.app.summary.get())
        self.assertGreater(len(self.app.tree.get_children(self.app.tree.get_children()[0])), 0)
        names = [self.app.table.item(item, 'values')[1] for item in self.app.table.get_children()]
        self.assertEqual(set(names), {'grace.md', 'grace.txt'})

    def test_selection_preview_and_layout_change_invalidates_copy(self):
        self.app.select_visible()
        self.assertEqual(len(self.app.selected), 2)
        self.app.destination.set(str(self.base))
        self.app.preview_export()
        self.assertIsNotNone(self.app.preview)
        self.assertFalse(self.app.copy_button.instate(['disabled']))
        self.assertFalse(self.app.preview[0].exists())
        self.app.layout.set('extension')
        self.assertIsNone(self.app.preview)
        self.assertTrue(self.app.copy_button.instate(['disabled']))

    def test_background_search_uses_explicit_formats(self):
        (self.source / 'grace.html').write_text('<p>Grace</p>')
        self.app.search()
        deadline = time.monotonic() + 8
        while self.app.busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.02)
        self.assertFalse(self.app.busy)
        self.assertEqual({row['ext'] for row in self.app.plan['files']}, {'.md', '.txt'})
        self.assertEqual(len(list((gui.STATION / 'OUTBOX').glob('*/plan.json'))), 1)


if __name__ == '__main__':
    unittest.main()
