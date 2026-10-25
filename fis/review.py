"""Persistent review queue: applied HTML never hides pending source renames."""
import time
from pathlib import Path
from fis.index import digest
from fis import preference
from fis.transaction import verify_plan


def identity(row):
    return digest([row['path'], row['sha256'], row['target']])


def reject(store, plan_id, expected_hash, rows, reason='Not my preferred name'):
    plan = store.get('plan', plan_id)
    verify_plan(plan)
    if plan['hash'] != expected_hash:
        raise ValueError('Plan changed; reload before rejecting')
    known = {r['id']: r for r in plan['rows'] if r['kind'] == 'rename'}
    if not rows or not set(rows) <= known.keys():
        raise ValueError('Select rename proposals to reject')
    with store.lock():
        for key in rows:
            row = known[key]
            store.put('review-decision', identity(row), {'at': time.time(), 'decision': 'rejected',
                       'plan': plan_id, 'hash': expected_hash, 'row': key, 'reason': reason})
            preference.record(store, plan, row, False, reason)
    return {'rejected': len(rows), 'learned': True, 'files_changed': 0}


def summaries(store):
    plans = store.all('plan')
    result, seen = [], set()
    applied_ids = set()
    for run in store.all('run'):
        if run['status'] == 'applied':
            approval = store.get('approval', run['approval'], {})
            applied_ids.update((run['plan'], r) for r in approval.get('rows', []))
    for plan in plans:
        # Only the newest proposal set for a root is active; old versions remain accessible by id.
        if plan['root'] in seen:
            continue
        seen.add(plan['root'])
        pending = []
        for row in plan['rows']:
            if row['kind'] != 'rename' or (plan['id'], row['id']) in applied_ids:
                continue
            if store.get('review-decision', identity(row)):
                continue
            if not Path(row['path']).is_file():
                continue
            pending.append(row['id'])
        html_pending = [r['id'] for r in plan['rows'] if r['kind']=='html' and (plan['id'],r['id']) not in applied_ids]
        completed = [r['id'] for r in plan['rows'] if (plan['id'], r['id']) in applied_ids]
        rejected = [r['id'] for r in plan['rows'] if r['kind']=='rename' and store.get('review-decision', identity(r))]
        result.append({'id': plan['id'], 'root': plan['root'], 'hash': plan['hash'], 'created': plan['created'],
                       'rows': len(plan['rows']), 'pending_renames': len(pending), 'pending_rows': pending,
                       'completed_rows': completed, 'rejected_rows': rejected,
                       'applied': not pending and not html_pending})
    return result
