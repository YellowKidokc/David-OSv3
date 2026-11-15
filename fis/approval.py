"""GUI decision transport. FIS validates and executes; GUI records the choice."""
import json
import os
import urllib.request
from shared.review import validate_receipt
from fis import transaction


def record_decision(plan, rows, decision, actor='David', note='', endpoint=None):
    endpoint = endpoint or os.environ.get('PREDICTION_GUI_URL', 'http://127.0.0.1:2831')
    payload = json.dumps({'plan': plan, 'rows': rows, 'decision': decision, 'actor': actor, 'note': note}).encode()
    req = urllib.request.Request(endpoint.rstrip('/') + '/v1/fis/decide', data=payload,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as response:
        receipt = json.load(response)
    return validate_receipt(plan, receipt)


def authorize(store, receipt):
    plan = store.get('plan', receipt.get('plan'))
    validate_receipt(plan, receipt)
    if receipt['decision'] != 'approved':
        raise PermissionError('only an explicit approval can authorize execution')
    with store.lock('decision'):
        existing = store.get('gui-decision', receipt['id'])
        if existing:
            raise PermissionError('decision receipt already consumed')
        token = transaction.approve(store, plan['id'], plan['hash'], receipt['rows'])
        store.put('gui-decision', receipt['id'], {'receipt': receipt, 'token': token})
        return token
