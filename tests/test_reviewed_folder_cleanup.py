from pathlib import Path
from engine.folder_merge import inventory,merge_group
from engine.reviewed_folder_cleanup import apply_reviewed


def prepare(tmp_path):
    scope=tmp_path/'sources';scope.mkdir()
    a=scope/'a';b=scope/'b';a.mkdir();b.mkdir()
    (a/'same.txt').write_text('same')
    (b/'same.txt').write_text('same')
    (a/'big.txt').write_text('x'*100)
    (a/'conflict.txt').write_text('original')
    (b/'conflict.txt').write_text('alternative')
    (b/'missing.txt').write_text('new')
    snapshots={str(p.resolve()):inventory(p) for p in (a,b)}
    receipt=merge_group(list(snapshots.values()),tmp_path/'staged',True)
    receipt['review']={'label':'example','roots':list(snapshots)}
    return scope,a,b,snapshots,receipt


def test_retirement_preserves_union_and_recovery(tmp_path):
    scope,a,b,snapshots,receipt=prepare(tmp_path)
    result=apply_reviewed(receipt,snapshots,scope,tmp_path/'recovery',approved=True,journal=tmp_path/'journal.jsonl')
    assert result['status']=='complete'
    assert (a/'missing.txt').read_text()=='new'
    assert len(list(a.glob('conflict*')))==2
    assert not b.exists()
    saved=result['recovered'][0]['recovery']
    assert inventory(Path(saved))['files']==snapshots[str(b.resolve())]['files']


def test_changed_source_blocks_all_mutation(tmp_path):
    scope,a,b,snapshots,receipt=prepare(tmp_path)
    (b/'missing.txt').write_text('changed')
    result=apply_reviewed(receipt,snapshots,scope,tmp_path/'recovery',approved=True,journal=tmp_path/'journal.jsonl')
    assert result['status']=='held' and b.exists()
    assert not (a/'missing.txt').exists()


def test_known_reference_blocks_cleanup(tmp_path):
    scope,a,b,snapshots,receipt=prepare(tmp_path)
    result=apply_reviewed(receipt,snapshots,scope,tmp_path/'recovery',approved=True,reference_hits=['live shortcut'],journal=tmp_path/'journal.jsonl')
    assert result['status']=='held' and b.exists()


def test_unapproved_scope_cannot_be_applied(tmp_path):
    scope,a,b,snapshots,receipt=prepare(tmp_path)
    result=apply_reviewed(receipt,snapshots,scope,tmp_path/'recovery',journal=tmp_path/'journal.jsonl')
    assert result['status']=='held' and b.exists()


def test_modified_staging_blocks_cleanup(tmp_path):
    scope,a,b,snapshots,receipt=prepare(tmp_path)
    (Path(receipt['destination'])/'extra.txt').write_text('unreviewed')
    result=apply_reviewed(receipt,snapshots,scope,tmp_path/'recovery',approved=True,journal=tmp_path/'journal.jsonl')
    assert result['status']=='held' and b.exists()
