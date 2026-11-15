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
