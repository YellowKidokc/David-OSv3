import copy
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
