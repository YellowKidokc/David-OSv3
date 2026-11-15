"""One immutable FIS plan/decision contract for producer, GUI and executor."""
import hashlib
import json

SCHEMA = 'fis.review-decision.v1'


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get('id'), str) or not plan.get('id'):
        raise ValueError('missing plan ID')
    if plan.get('hash') != digest({k: v for k, v in plan.items() if k != 'hash'}):
        raise ValueError('plan hash mismatch')
    rows = plan.get('rows')
    if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('id'), str) for r in rows):
        raise ValueError('invalid plan rows')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate row IDs')
    return plan


def decision_receipt(plan, rows, decision, actor, note=''):
    validate_plan(plan)
    if decision not in {'approved', 'rejected', 'held'} or not isinstance(actor, str) or not actor.strip():
        raise ValueError('explicit decision and actor required')
    if not isinstance(rows, list) or not rows or any(not isinstance(r, str) for r in rows) or len(set(rows)) != len(rows):
        raise ValueError('select distinct proposal rows')
    known = {r['id']: r for r in plan['rows']}
    if not set(rows) <= known.keys():
        raise ValueError('unknown proposal row')
    if decision == 'approved' and any(known[r].get('flag') for r in rows):
        raise ValueError('held proposal cannot be approved')
    value = {'schema': SCHEMA, 'plan': plan['id'], 'hash': plan['hash'],
             'rows': sorted(rows), 'decision': decision, 'actor': actor, 'note': note}
    return {**value, 'id': digest(value)}


def validate_receipt(plan, receipt):
    if not isinstance(receipt, dict):
        raise ValueError('decision receipt required')
    expected = decision_receipt(plan, receipt.get('rows'), receipt.get('decision'), receipt.get('actor'), receipt.get('note', ''))
    if receipt != expected:
        raise ValueError('decision does not bind to this exact plan')
    return receipt
