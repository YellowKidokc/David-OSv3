from engine.desktop_merge_survey import name_key, survey


def test_name_normalization_is_only_a_candidate_key():
    assert name_key('AI-Crew (2)') == name_key('AI Crew')
    assert name_key('Master Equation') != name_key('Master EXCEL')


def test_survey_reports_excluded_content_instead_of_claiming_complete(tmp_path):
    (tmp_path/'actual.txt').write_text('content')
    (tmp_path/'node_modules').mkdir()
    (tmp_path/'node_modules'/'dependency.js').write_text('library')
    (tmp_path/'empty').mkdir()
    result=survey(tmp_path)
    assert set(result['files'])=={'actual.txt'}
    assert result['excluded']==['node_modules']
    assert 'empty' in result['directories']
    assert result['bytes']==7
