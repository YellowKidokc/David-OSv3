import csv
import tempfile
import unittest
from pathlib import Path

from folder_intelligence import compare_profiles, profile_folder
from large_list_reconciler import index_roots, load_wanted, reconcile


class FileIntelligenceTests(unittest.TestCase):
    def test_large_list_does_not_collapse_same_name_collisions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "paper.md").write_text("one", encoding="utf-8")
            (root / "b" / "paper.md").write_text("different", encoding="utf-8")
            wanted_path = root / "wanted.csv"
            with wanted_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["filename"])
                writer.writeheader()
                writer.writerow({"filename": "paper.md"})
            wanted = load_wanted(wanted_path)
            index, errors = index_roots([root])
            result = reconcile(wanted, index)[0]
            self.assertFalse(errors)
            self.assertEqual(result["status"], "ambiguous")
            self.assertEqual(result["candidate_count"], 2)
            self.assertFalse(result["mutation_authorized"])

    def test_profiles_compare_without_folder_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            left, right = root / "unrelated-label-a", root / "different-label-b"
            left.mkdir()
            right.mkdir()
            (left / "first.md").write_text("same", encoding="utf-8")
            (right / "second.md").write_text("same", encoding="utf-8")
            relation = compare_profiles(profile_folder(left, "all"), profile_folder(right, "all"))
            self.assertEqual(relation["directional_evidence"], "same_content_set")
            self.assertEqual(relation["shared_exact_hashes"], 1)
            self.assertFalse(relation["mutation_authorized"])


if __name__ == "__main__":
    unittest.main()
