import tempfile
import unittest
from pathlib import Path

import canon_guard


class CanonGuardTests(unittest.TestCase):
    def test_equation_normalization_unicode_and_latex(self):
        a = canon_guard.normalize_equation("χ = G · M · C")
        b = canon_guard.normalize_equation(r"\chi=G\cdot M\cdot C")
        self.assertEqual(a, b)

    def test_version_parser(self):
        self.assertEqual(canon_guard.parse_version("v3.2"), (3, 2, 0))
        self.assertIsNone(canon_guard.parse_version("July final"))

    def test_unregistered_canon_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "claim.md"
            path.write_text("# Claim\n\nStatus: CANON\n", encoding="utf-8")
            doc = canon_guard.parse_document(path, root)
            findings = canon_guard.check_false_canon(doc, set())
            self.assertEqual(findings[0].code, "UNREGISTERED_CANON")

    def test_extracts_display_equation(self):
        equations = canon_guard.extract_equations("Before\n$$χ = G \\cdot M$$\nAfter\n")
        self.assertEqual(len(equations), 1)
        self.assertEqual(equations[0].line, 2)

    def test_rule_can_exclude_canonical_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "canon" / "rule.md"
            path.parent.mkdir()
            path.write_text("This does not prove theology.\n", encoding="utf-8")
            doc = canon_guard.parse_document(path, root)
            manifest = {"claims": [{
                "id": "HEDGE", "mode": "forbid", "pattern": "does not prove theology",
                "message": "bare hedge", "scope": ["**/*.md"],
                "exclude_scope": ["canon/rule.md"],
            }]}
            self.assertEqual(canon_guard.apply_claim_rules(doc, manifest), [])


if __name__ == "__main__":
    unittest.main()
