"""04_ADAPT — legacy glossary cards get a mechanical mim.v1 stamp.

The adapter translates what can be translated without judgment (type, name,
status→standing, source_file) and leaves the judgment facets blank for the
classifier + David. Originals are never touched; output lands in an outbox.
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "04_ADAPT"))
sys.path.insert(0, str(REPO / "03_CLASSIFY" / "02_CLASSIFICATION"))
sys.path.insert(0, str(REPO / "03_CLASSIFY" / "00_SHARED"))

import adapt_cards  # noqa: E402
from harness.adapters import sidecars  # noqa: E402

# same contract the reviewer enforces (gui/review.py REQUIRED)
REQUIRED = ("sidecar", "subject", "source", "source_file", "standing", "folder_class")

GLOSSARY_CARD = '''---
type: "definition"
status: "draft"
tier: "canonical"
term_class: "system_specific"
wikipedia_checked: no
source_file: "O:/_Theophysics_v3/00_SYSTEM/Glossary/Wheeler.md"
name: "Wheeler"
aliases: []
axioms_required: []
laws: []
related_terms:
  - term: "It from Bit"
    relation: "extends"
  - term: "Participatory Universe"
    relation: "requires"
canonical_candidate_reason: "Root term used across the framework"
created: 2026-07-01
updated: 2026-07-02
---

# Wheeler

It from Bit: every physical quantity derives its meaning from binary yes/no answers.
'''


def _roundtrip(tmp_path, text, stem="Wheeler"):
    out = adapt_cards.convert_card_text(text, stem)
    assert out is not None
    p = tmp_path / f"{stem}.md"
    p.write_text(out, encoding="utf-8")
    return p, *sidecars.parse_card(p)


def test_glossary_card_converts_to_readable_mim_v1(tmp_path):
    p, fields, tags = _roundtrip(tmp_path, GLOSSARY_CARD)
    assert fields, "converted card must pass the mim.v1 gate in parse_card"
    assert fields["sidecar"] == "mim.v1"
    assert fields["subject"] == "Wheeler" == p.stem
    assert fields["source"] == "[[Wheeler]]"
    assert fields["source_file"] == "O:/_Theophysics_v3/00_SYSTEM/Glossary/Wheeler.md"
    assert fields["standing"] == "draft"
    assert fields["folder_class"] == "glossary"
    for req in REQUIRED:
        assert fields.get(req), f"missing required field: {req}"
    assert "sidecar" in tags and "subject" in tags


def test_provenance_fields_present(tmp_path):
    _, fields, _ = _roundtrip(tmp_path, GLOSSARY_CARD)
    assert fields["adapted_from"] == "glossary-card"
    assert fields["adapted_at"]


def test_original_fields_and_nested_lists_survive_verbatim(tmp_path):
    out = adapt_cards.convert_card_text(GLOSSARY_CARD, "Wheeler")
    assert '  - term: "It from Bit"\n    relation: "extends"' in out
    assert 'term_class: "system_specific"' in out
    assert 'canonical_candidate_reason: "Root term used across the framework"' in out
    assert 'tier: "canonical"' in out
    # body after the closing fence is untouched
    assert "# Wheeler" in out
    assert "binary yes/no answers" in out


def test_unknown_status_becomes_blank_standing_for_the_classifier(tmp_path):
    card = GLOSSARY_CARD.replace('status: "draft"', 'status: "needs_review"')
    out = adapt_cards.convert_card_text(card, "Wheeler")
    assert re.search(r"^standing:\s*$", out, re.M), \
        "a status off the closed list must NOT be copied into standing"


def test_older_file_path_variant_maps_to_source_file(tmp_path):
    card = '''---
uuid: 3be6f05a-6374-5536-bf7c-2dbb05a27a55
title: ADV — Adversary
type: note
status: draft
file_path: Logos zright\\Misc\\ADV.md
---

# ADV — Adversary
'''
    _, fields, _ = _roundtrip(tmp_path, card, "ADV")
    assert fields["source_file"] == "Logos zright\\Misc\\ADV.md"
    assert fields["source"] == "[[ADV]]"
    assert fields["standing"] == "draft"


def test_convert_folder_skips_stamped_counts_failures_never_touches_source(tmp_path):
    src = tmp_path / "in"
    dst = tmp_path / "out"
    src.mkdir()
    (src / "Wheeler.md").write_text(GLOSSARY_CARD, encoding="utf-8")
    stamped = adapt_cards.convert_card_text(GLOSSARY_CARD, "Already")
    (src / "Already.md").write_text(stamped, encoding="utf-8")
    (src / "Notes.md").write_text("# just notes\nno frontmatter here\n", encoding="utf-8")

    stats = adapt_cards.convert_folder(src, dst)

    assert stats["converted"] == 1
    assert stats["skipped"] == 1
    assert [name for name, _ in stats["failed"]] == ["Notes.md"]
    assert (dst / "Wheeler.md").exists()
    assert not (dst / "Already.md").exists()
    assert not (dst / "Notes.md").exists()
    assert (src / "Wheeler.md").read_text(encoding="utf-8") == GLOSSARY_CARD


def test_card_diagnosis_distinguishes_legacy_card_from_no_frontmatter(tmp_path):
    legacy = tmp_path / "Wheeler.md"
    legacy.write_text(GLOSSARY_CARD, encoding="utf-8")
    plain = tmp_path / "notes.md"
    plain.write_text("# notes\n", encoding="utf-8")
    idx = tmp_path / "00_INDEX.md"
    idx.write_text("---\nsidecar: mim.v1\ntype: subject-index\n---\n", encoding="utf-8")

    d_legacy = sidecars.card_diagnosis(legacy)
    assert "04_ADAPT" in d_legacy and "definition" in d_legacy
    assert "no frontmatter" in sidecars.card_diagnosis(plain)
    assert "subject index" in sidecars.card_diagnosis(idx)
