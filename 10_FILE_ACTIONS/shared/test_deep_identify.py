"""Acceptance tests for deep_identify.py — each test is a case the Nov 12 crew used to BREAK v0.

Run: python test_deep_identify.py   (plain asserts, no pytest needed)
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import deep_identify as di

PROSE_A = "Entropy grace coherence covenant lattice measurement observer collapse " * 3
PROSE_B = "Fencing invoice concrete gate posts hinge welding customer schedule " * 3


def run(root: Path):
    cards, fams, stats = di.scan_folder(root)
    return {c.name: c for c in cards}, fams, stats


def test_reciprocal_links_different_names():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "alpha_thesis.md").write_text("# Alpha\nSee [[beta_response]] for the reply.\n" + PROSE_A)
        (r / "beta_response.md").write_text("# Beta\nAnswering [[alpha_thesis]].\n" + PROSE_B)
        cards, fams, _ = run(r)
        assert len(fams) == 1, f"expected 1 family, got {len(fams)}"
        assert any(e.startswith("link") for e in fams[0].evidence)
        assert cards["alpha_thesis.md"].family_id == cards["beta_response.md"].family_id
    print("PASS  differently named files with reciprocal links form one family")


def test_same_name_unrelated_content_not_merged():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "a").mkdir(); (r / "b").mkdir()
        (r / "a" / "Notes.md").write_text("# Notes\n" + PROSE_A)
        (r / "b" / "Notes.md").write_text("# Notes\n" + PROSE_B)
        _, fams, stats = run(r)
        assert len(fams) == 0, f"title root alone must not merge; got {len(fams)} families"
        assert stats["weak_candidate_pairs"] >= 1
    print("PASS  same title, unrelated content -> weak candidate only, no family")


def test_repeated_position_completeness():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "x").mkdir()
        (r / "Paper_01.md").write_text("# One\n" + PROSE_A)
        (r / "x" / "Paper_01.md").write_text("# One again\n" + PROSE_A)
        (r / "Paper_02.md").write_text("# Two\n" + PROSE_A)
        _, fams, _ = run(r)
        assert len(fams) == 1
        f = fams[0]
        assert f.completeness <= 1.0, f"completeness {f.completeness}"
        assert "1" in f.competing_versions and len(f.competing_versions["1"]) == 2
    print("PASS  repeated Paper_01 -> completeness 1.0, competing version flagged")


def test_zero_marker_prose_abstains():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "plain.md").write_text("The river was cold and the light was low over the field. " * 20)
        cards, _, _ = run(r)
        assert cards["plain.md"].doc_type == "unknown", cards["plain.md"].doc_type
    print("PASS  marker-free prose -> doc_type unknown (abstains)")


def test_nested_git_protected():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "proj" / ".git").mkdir(parents=True)
        (r / "proj" / "src").mkdir()
        (r / "proj" / "src" / "main.py").write_text("print(1)\n")
        (r / "loose.md").write_text("# Loose\n" + PROSE_A)
        cards, _, _ = run(r)
        m = cards["main.py"]
        assert m.is_protected and not m.can_rename and not m.can_move, (m.is_protected, m.can_rename)
        assert not cards["loose.md"].is_protected
    print("PASS  file under nested .git -> protected, not renameable/movable")


def test_empty_rerun_leaves_no_stale_rows():
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out:
        r, o = Path(d), Path(out)
        (r / "Paper_01.md").write_text("# One\n" + PROSE_A)
        (r / "Paper_02.md").write_text("# Two\n" + PROSE_A)
        di.write_report(*di.scan_folder(r), o)
        for p in r.iterdir():
            p.unlink()
        di.write_report(*di.scan_folder(r), o)
        for name in ("file_cards.csv", "families.csv", "orphans.csv"):
            rows = list(csv.reader((o / name).open(encoding="utf-8")))
            assert len(rows) == 1, f"{name} has {len(rows)-1} stale rows"
        assert json.loads((o / "deep_identify.json").read_text(encoding="utf-8"))["stats"]["files_scanned"] == 0
    print("PASS  empty rerun -> header-only CSVs, no stale rows")


def test_pdf_flagged_not_decoded():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "scan.pdf").write_bytes(b"%PDF-1.4 binary \x00\x01\x02")
        cards, _, stats = run(r)
        assert cards["scan.pdf"].extraction_status == "unsupported_binary_format"
        assert stats["extraction_status"].get("unsupported_binary_format") == 1
    print("PASS  PDF -> extraction_status unsupported_binary_format")


def test_family_id_stable():
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        (r / "Law_01.md").write_text("# L1\n" + PROSE_A)
        (r / "Law_02.md").write_text("# L2\n" + PROSE_A)
        _, f1, _ = run(r)
        _, f2, _ = run(r)
        assert f1[0].family_id == f2[0].family_id
    print("PASS  same input -> same family_id across runs")


def test_real_folder_shapes_math_is_moral():
    """Shapes found in O-09_Math_Is_Moral on 2026-11-12: one document code with several artifacts,
    one paper under three stage codes, papers with YAML frontmatter."""
    fm = "---\ntitle: x\nstatus: draft\n---\n"
    body = "# Abstract\nThis paper argues operators boundary conditions morality mathematics judgment completion logic. " * 8
    with tempfile.TemporaryDirectory() as d:
        r = Path(d)
        for n in ("FT-003_PAPER.md", "FT-003_FACTS_CARD.md", "FT-003_SCORED.md"):
            (r / n).write_text(fm + "# " + n + "\n" + PROSE_B * 4)
        (r / "DT-001_Math_Is_Moral.canonical.md").write_text(fm + body)
        (r / "FP-002_MATH_IS_MORAL.md").write_text(fm + body)
        (r / "Math_Is_Moral.md").write_text(body)
        (r / "newton_notes.md").write_text("# Notes\ntodo: " + PROSE_A)
        cards, fams, _ = run(r)
        ft = {cards[n].family_id for n in ("FT-003_PAPER.md", "FT-003_FACTS_CARD.md", "FT-003_SCORED.md")}
        mim = {cards[n].family_id for n in ("DT-001_Math_Is_Moral.canonical.md", "FP-002_MATH_IS_MORAL.md", "Math_Is_Moral.md")}
        assert len(ft) == 1 and "" not in ft, "FT-003 artifacts must be one family"
        assert len(mim) == 1 and "" not in mim, "three stages of Math Is Moral must be one family"
        assert ft != mim
        fam_ft = next(f for f in fams if f.family_id in ft)
        assert fam_ft.family_name == "FT-003" and not fam_ft.competing_versions, (fam_ft.family_name, fam_ft.competing_versions)
        assert cards["FP-002_MATH_IS_MORAL.md"].doc_type == "paper", cards["FP-002_MATH_IS_MORAL.md"].doc_type
        assert di.extract_title_root("newton_notes.md") == "newton notes"
    print("PASS  real shapes: doc-code artifacts = one family, staged paper = one family, frontmatter paper = paper")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
