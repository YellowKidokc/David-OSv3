from pathlib import Path
import pytest
from engine.folder_merge import inventory, discover, merge_group, run


def folder(root, name, files):
    p = root / name
    p.mkdir()
    for rel, text in files.items():
        target = p / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return p


def test_discovery_uses_contents_even_when_names_differ(tmp_path):
    shared = {f'{i}.txt': f'shared {i}' for i in range(4)}
    a = folder(tmp_path, 'alpha', shared)
    b = folder(tmp_path, 'different', {**shared, 'new.txt': 'new'})
    c = folder(tmp_path, 'alpha (1)', {'other.txt': 'unrelated'})
    pairs, groups = discover([inventory(p) for p in (a,b,c)])
    assert len(pairs) == 3
    assert [{Path(i['root']).name for i in g} for g in groups] == [{'alpha', 'different'}]


def test_union_conflicts_empty_directories_and_rerun(tmp_path):
    a = folder(tmp_path, 'a', {'sub/same.txt':'same','conflict.txt':'one','unique.txt':'unique'})
    b = folder(tmp_path, 'b', {'sub/same.txt':'same','conflict.txt':'other','missing.txt':'added'})
    (a/'empty').mkdir()
    items = [inventory(a),inventory(b)]
    dest = tmp_path/'merged'
    first = merge_group(items,dest,True)
    assert first['verified'] and not first['cleanup_authorized']
    assert (dest/'empty').is_dir()
    assert len(list(dest.glob('conflict*'))) == 2
    assert (dest/'missing.txt').read_text() == 'added'
    second = merge_group(items,dest,True)
    assert second['verified']
    assert all(x['status']=='skipped_identical' for x in second['operations'])
    assert inventory(a)['files']==items[0]['files']
    assert inventory(b)['files']==items[1]['files']


def test_changed_source_blocks_verification(tmp_path):
    a=folder(tmp_path,'a',{'x.txt':'before'})
    item=inventory(a)
    (a/'x.txt').write_text('after')
    result=merge_group([item],tmp_path/'merged',True)
    assert not result['verified'] and result['errors']


def test_preview_creates_no_merge_destination(tmp_path):
    a=folder(tmp_path,'a',{'x.txt':'x'})
    assert not merge_group([inventory(a)],tmp_path/'merged')['verified']
    assert not (tmp_path/'merged').exists()


def test_existing_target_never_overwritten(tmp_path):
    a=folder(tmp_path,'a',{'x.txt':'source'})
    dest=folder(tmp_path,'dest',{'x.txt':'unrelated'})
    assert not merge_group([inventory(a)],dest,True)['verified']
    assert (dest/'x.txt').read_text()=='unrelated'


def test_nested_scope_rejected(tmp_path):
    a=folder(tmp_path,'a',{'x.txt':'x'})
    with pytest.raises(ValueError):
        merge_group([inventory(a)],a/'nested',True)


def test_same_content_at_different_paths_retains_both_paths(tmp_path):
    a=folder(tmp_path,'a',{'first.txt':'same bytes'})
    b=folder(tmp_path,'b',{'second.txt':'same bytes'})
    dest=tmp_path/'merged'
    assert merge_group([inventory(a),inventory(b)],dest,True)['verified']
    assert (dest/'first.txt').read_bytes()==(dest/'second.txt').read_bytes()


def test_incomplete_inventory_is_refused(tmp_path):
    a=folder(tmp_path,'a',{'first.txt':'x'})
    item=inventory(a)
    item['errors'].append('unreadable source')
    with pytest.raises(ValueError,match='Incomplete'):
        merge_group([item],tmp_path/'merged',True)


def test_small_exact_replicas_are_not_missed(tmp_path):
    a=folder(tmp_path,'a',{'only.txt':'real content'})
    b=folder(tmp_path,'b',{'only.txt':'real content'})
    pairs,groups=discover([inventory(a),inventory(b)])
    assert pairs[0]['exact_replica'] and len(groups)==1


def test_parallel_inventory_matches_serial(tmp_path):
    a=folder(tmp_path,'a',{f'sub/{i}.txt':f'bytes {i}' for i in range(30)})
    serial=inventory(a)
    parallel=inventory(a,workers=4)
    assert parallel['files']==serial['files']
    assert sorted(parallel['directories'])==sorted(serial['directories'])
    assert parallel['errors']==serial['errors']==[]
