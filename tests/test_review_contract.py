import copy
from pathlib import Path
import pytest
from fis import service, transaction, approval
from fis.index import Store
from shared.review import decision_receipt, validate_receipt


def test_approval_binds_exact_rows_plan_and_survives_restart(tmp_path):
    root = tmp_path/'source'; root.mkdir()
    (root/'draft notes.txt').write_text('A method and evidence')
    store = Store(tmp_path/'state')
    service.configure_root(store, root)
    plan = service.make_plan(store, root, html=False)
    rows = [r['id'] for r in plan['rows'] if not r['flag']]
    receipt = decision_receipt(plan, rows, 'approved', 'David')
    bad = copy.deepcopy(receipt); bad['hash'] = 'changed'
    with pytest.raises(ValueError): validate_receipt(plan, bad)
    token = approval.authorize(store, receipt)
    with pytest.raises(PermissionError): approval.authorize(Store(tmp_path/'state'), receipt)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    run = transaction.apply(Store(tmp_path/'state'), plan['id'], token)
    assert run['status'] == 'applied'
    new_path = next(root.iterdir())
    assert store.registry.reference(new_path)['uuid7'] == plan['rows'][0]['file']['registry_uuid']
    assert transaction.undo(Store(tmp_path/'state'), run['id'])['conflicts'] == []
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


def test_flagged_unknown_and_rejected_rows_cannot_authorize(tmp_path):
    store = Store(tmp_path/'state')
    plan = {'id':'plan', 'rows':[{'id':'held', 'flag':'collision'}]}
    plan['hash'] = transaction.plan_hash(plan)
    store.put('plan', plan['id'], plan)
    with pytest.raises(ValueError): decision_receipt(plan, ['unknown'], 'approved', 'David')
    with pytest.raises(ValueError): decision_receipt(plan, ['held'], 'approved', 'David')
    rejected = decision_receipt(plan, ['held'], 'rejected', 'David')
    with pytest.raises(PermissionError): approval.authorize(store, rejected)


def test_registry_target_conflict_stops_before_source_mutation(tmp_path):
    root=tmp_path/'source';root.mkdir()
    source=root/'notes.txt';source.write_text('A method and evidence')
    store=Store(tmp_path/'state');service.configure_root(store,root)
    plan=service.make_plan(store,root,html=False)
    row=plan['rows'][0]
    store.registry.reference(row['target'])  # distinct earlier observation, even though file is now absent
    token=transaction.approve(store,plan['id'],plan['hash'],[row['id']])
    with pytest.raises(ValueError,match='another registry'):
        transaction.apply(store,plan['id'],token)
    assert source.read_text()=='A method and evidence'
    assert not Path(row['target']).exists()


def test_restart_recovers_file_move_before_registry_commit(tmp_path, monkeypatch):
    root=tmp_path/'source';root.mkdir()
    source=root/'notes.txt';source.write_text('A method and evidence')
    store=Store(tmp_path/'state');service.configure_root(store,root)
    plan=service.make_plan(store,root,html=False)
    row=plan['rows'][0]
    token=transaction.approve(store,plan['id'],plan['hash'],[row['id']])
    def interrupted(*args, **kwargs): raise RuntimeError('interrupted before registry commit')
    monkeypatch.setattr(store.registry,'relocate',interrupted)
    with pytest.raises(RuntimeError): transaction.apply(store,plan['id'],token)
    restarted=Store(tmp_path/'state')
    run=restarted.all('run')[0]
    assert transaction.undo(restarted,run['id'])['conflicts']==[]
    assert source.read_text()=='A method and evidence'
    assert restarted.registry.reference(source)['uuid7']==row['file']['registry_uuid']
