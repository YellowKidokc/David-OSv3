"""Lock the extracted App 160 grammar, scoring and folder fallback."""
import json
import os
import time
from pathlib import Path

import pytest
from shared import meq_namer as m


def test_slot_and_pair_order():
    chi = dict.fromkeys(m.SLOTS, 3)
    assert m.meq_namer_string(chi) == 'G3 M3 E3 S3 T3 K3 R3 Q3 F3 C3 :: [G.C] [M.F] [E.Q] [S.R] [T.K]'
    assert m.meq_namer_short({'K': 2, 'G': 1}) == 'G1 K2 :: [G.C] [T.K]'
    assert m.meq_namer_string({'G': 1}).startswith('G1 M0 E0 S0 T0 K0 R0 Q0 F0 C0 :: ')


@pytest.mark.parametrize('chi', [{}, dict.fromkeys(m.SLOTS, 0)])
def test_unscored(chi):
    assert m.meq_namer_string(chi) == m.meq_namer_short(chi) == ''
    assert (m.meq_namer_short(chi) or m.meq_namer_string(chi) or m.UNSCORED) == 'UNSCORED'


@pytest.mark.parametrize('text,expected', [('', 0), ('charis', 1), ('charis geodesic', 1),
    ('charis geodesic unmerited', 2), ('charis geodesic unmerited negentropic provision', 2),
    ('charis geodesic unmerited negentropic provision sovereign', 3)])
def test_scoring_boundaries(text, expected):
    assert m.score_chi_factor(text.upper(), 'G') == expected


def test_legacy_substrings_and_repeated_keywords():
    assert m.score_chi_factor('logos', 'K') == 1  # two entries, still score 1
    assert m.score_chi_factor('logos shannon', 'K') == 2  # repeated keyword counts
    assert m.score_chi_factor('graceful', 'G') == 1  # substring, not token matching


@pytest.mark.parametrize('title,sample,prefix', [('Notes', 'ordinary', 'LOSS'),
    ('Master-Equation', '', 'MEQ'), ('Notes', 'chi_field', 'MEQ'), ('', '', 'LOSS')])
def test_lossless_address(title, sample, prefix):
    stamp = 1700000000
    r = m.propose_lossless_address(title, sample, stamp)
    from datetime import datetime
    assert r['address'] == f'{prefix}__{m.lossless_slug(title)}__{datetime.fromtimestamp(stamp):%Y-%m-%d}'
    assert r['basis'] == 'title_and_local_content_sample'
    assert m.lossless_slug('') == 'folder'
    assert len(m.lossless_slug('x' * 100)) == 40


def test_folder_aggregate_excludes_unscored_and_keeps_rounding():
    rows = [{'local_classification_json': json.dumps({'chi': c})} for c in ({'G': 1}, {}, {'G': 2, 'K': 3})]
    assert m.folder_meq_aggregate(rows) == m.meq_namer_string({'G': 2, 'K': 2})
    assert m.folder_meq_aggregate([]) == ''


def test_folder_address_falls_back_to_local_folder_metadata(tmp_path):
    from fis.fis_folder_memory import folder_lossless_address
    folder = tmp_path / 'Ordinary-folder'
    folder.mkdir()
    result = folder_lossless_address(folder, [])
    assert result['address'].startswith('LOSS__Ordinary_folder__')
    assert result['trigger'] is None
    (folder / 'Master_Equation.md').write_text('grace', encoding='utf-8')
    result = folder_lossless_address(folder, [folder / 'Master_Equation.md'])
    assert result['mode'] == 'meq'


def test_fis_classifier_uses_shared_scoring():
    from fis import fis_classifier
    assert fis_classifier.CHI_SIGNALS is m.CHI_SIGNALS
    assert fis_classifier.score_chi_factor is m.score_chi_factor


def test_retired_notes_are_preserved_instead_of_deleted(tmp_path):
    from fis.fis_folder_memory import wipe_existing_fisnotes
    (tmp_path / '.fisnote').write_bytes(b'folder evidence')
    (tmp_path / 'old.md.fisnote').write_bytes(b'file evidence')
    assert wipe_existing_fisnotes(tmp_path) == 2
    assert not list(tmp_path.glob('*.fisnote'))
    assert {p.read_bytes() for p in tmp_path.glob('.fisnote.legacy.*')} == {b'folder evidence', b'file evidence'}
