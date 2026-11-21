import tempfile
import unittest
from pathlib import Path

from series_aware_flatten import ClassificationRegistry, add_classification_index, build_plan


class SeriesAwareFlattenTests(unittest.TestCase):
    def test_detected_series_moves_as_one_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            series = root / "wrapper" / "papers"
            series.mkdir(parents=True)
            for number in (1, 2, 3):
                (series / f"Paper {number} Example.md").write_text(f"# Paper {number}", encoding="utf-8")
            plan = build_plan(root)
            row = next(row for row in plan["decisions"] if row["source"] == str(series))
            self.assertEqual(row["action"], "LIFT_SERIES_FOLDER")
            self.assertTrue(row["series_key"])
            self.assertEqual(row["recursive_document_count"], 3)
            self.assertFalse(plan["source_mutations"])

    def test_destination_collision_is_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "same").mkdir()
            nested = root / "wrapper" / "same"
            nested.mkdir(parents=True)
            (nested / "a.md").write_text("a", encoding="utf-8")
            plan = build_plan(root)
            row = next(row for row in plan["decisions"] if row["source"] == str(nested))
            self.assertEqual(row["action"], "HOLD_COLLISION")
            self.assertTrue(row["collision"])

    def test_archives_are_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "wrapper" / "Chapter Archive"
            archive.mkdir(parents=True)
            (archive / "old.md").write_text("old", encoding="utf-8")
            plan = build_plan(root)
            self.assertTrue(any(row["path"] == str(archive) for row in plan["protected"]))

    def test_master_workbook_filename_match_preserves_series(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            series = root / "wrapper" / "unknown-folder-name"
            series.mkdir(parents=True)
            for name in ("Alpha.md", "Beta.md"):
                (series / name).write_text("paper", encoding="utf-8")
            registry = ClassificationRegistry(
                workbook="master.xlsx",
                workbook_sha256="abc",
                family_aliases={},
                package_aliases={},
                filename_series={
                    "alpha.md": ("MIM",),
                    "beta.md": ("MIM",),
                },
            )
            plan = build_plan(root, registry)
            row = next(row for row in plan["decisions"] if row["source"] == str(series))
            self.assertEqual(row["action"], "LIFT_SERIES_FOLDER")
            self.assertEqual(row["series_key"], "MIM")

    def test_tsv_index_adds_current_file_assignments(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / "index.txt"
            index.write_text("series\tfile_path\nCRWN\tMaster/Alpha.md\n", encoding="utf-8")
            registry = ClassificationRegistry("master.xlsx", "abc", {}, {}, {})
            updated = add_classification_index(registry, index)
            self.assertEqual(updated.filename_series["alpha.md"], ("CRWN",))
            self.assertEqual(updated.series_record_counts["CRWN"], 1)
            self.assertEqual(updated.series_unique_filename_counts["CRWN"], 1)
            self.assertEqual(updated.index_file, str(index.resolve()))


if __name__ == "__main__":
    unittest.main()
