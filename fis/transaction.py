"""Plan-bound mutation, durable intent journal, reversible moves, no deletion."""
import base64
import hashlib
import os
import time
from pathlib import Path
from fis import gate
from fis.fingerprint import sha256_file
from fis.index import canonical, digest, uid


def plan_hash(plan):
    return digest({k: v for k, v in plan.items() if k != 'hash'})


def verify_plan(plan):
    if not plan or plan.get('hash') != plan_hash(plan):
        raise ValueError('Plan is missing or has changed; rescan and approve again')


def approve(store, plan_id, expected_hash, rows=None, folders=None, automatic=False):
    with store.lock():
        plan = store.get('plan', plan_id)
        verify_plan(plan)
        if plan['hash'] != expected_hash:
            raise ValueError('Approval does not match the exact plan hash')
        chosen = {r['id'] for r in plan['rows'] if not r['flag']} if rows is None else set(rows)
        if not chosen <= {r['id'] for r in plan['rows']}:
            raise ValueError('Unknown plan row')
        if any(r['flag'] for r in plan['rows'] if r['id'] in chosen):
            raise PermissionError('Flagged rows are held for review; resolve and replan')
        if folders:
            chosen &= {r['id'] for r in plan['rows'] if r['folder'] in folders}
        if automatic:
            if any(r['kind'] == 'rename' for r in plan['rows'] if r['id'] in chosen):
                raise PermissionError('Crawler cannot authorize renames')
            config = gate.policy(store)
            if not any(gate.under(plan['root'], x) for x in config['html_roots']):
                raise PermissionError('HTML automation is not approved for this root')
        token = uid()
        store.put('approval', token, {'id': token, 'plan': plan_id, 'hash': expected_hash,
                  'rows': sorted(chosen), 'source': 'approved-html-root-policy' if automatic else 'human',
                  'policy_hash': digest(gate.policy(store)), 'created': time.time(), 'used': False})
        return token


def selected_ops(plan, rows, run, home):
    operations = []
    for row in plan['rows']:
        if row['id'] not in rows:
            continue
        if row['kind'] == 'rename':
            operations.append({'kind': 'move', 'src': row['path'], 'dst': row['target'],
                               'hash': row['sha256'], 'folder': row['folder']})
        elif row['kind'] == 'html':
            p = Path(row['path'])
            mirrored = Path(row['folder']).relative_to(plan['root'])
            if row['before_hash']:
                operations.append({'kind': 'move', 'src': str(p),
                   'dst': str(home/'archive'/run/'previous-html'/mirrored/p.name),
                   'hash': row['before_hash'], 'folder': row['folder']})
            for note in row['legacy']:
                operations.append({'kind': 'move', 'src': note['path'],
                   'dst': str(home/'archive'/run/'notes'/mirrored/Path(note['path']).name),
                   'hash': note['sha256'], 'folder': row['folder']})
            content = row['content'].replace('RUN_ID_PLACEHOLDER', run).encode('utf-8')
            operations.append({'kind': 'write', 'dst': str(p), 'content': base64.b64encode(content).decode(),
                               'hash': hashlib.sha256(content).hexdigest(), 'folder': row['folder']})
    return operations


def preflight(store, plan, approval):
    verify_plan(plan)
    if approval['hash'] != plan['hash'] or approval['policy_hash'] != digest(gate.policy(store)):
        raise PermissionError('Plan or policy changed after approval')
    if approval.get('used'):
        raise PermissionError('Approval already consumed')
    selected = [r for r in plan['rows'] if r['id'] in approval['rows']]
    if not selected:
        raise ValueError('No rows approved')
    paths = [r['path'] for r in selected]
    gate.check(store, plan['root'], paths)
    if Path(plan['root']).stat().st_dev != store.home.stat().st_dev:
        raise PermissionError('Archive/state must be on the source volume for reversible no-delete moves')
    for r in selected:
        p = Path(r['path'])
        if r['kind'] == 'rename':
            target = Path(r['target'])
            gate.check(store, plan['root'], [target])
            if target.parent != p.parent or target.name in {'.', '..'}:
                raise PermissionError('Rename must stay in its folder')
            if target.exists():
                raise FileExistsError(target)
            if not p.is_file() or sha256_file(p) != r['sha256']:
                raise ValueError('Source changed after plan: '+str(p))
        else:
            before = sha256_file(p) if p.is_file() else None
            if before != r['before_hash']:
                raise ValueError('HTML changed after plan: '+str(p))
            for source in r['sources'] + r['legacy']:
                gate.check(store, plan['root'], [source['path']])
                if not Path(source['path']).is_file() or sha256_file(source['path']) != source['sha256']:
                    raise ValueError('Source or note changed after plan: '+source['path'])
    return selected


def _move(src, dst):
    src, dst = Path(src), Path(dst)
    if dst.exists():
        raise FileExistsError(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Move, not copy/delete. Cross-volume moves deliberately fail before losing a source.
    os.rename(src, dst)


def apply(store, plan_id, token, fail_after=None):
    with store.lock():
        plan, approval = store.get('plan', plan_id), store.get('approval', token)
        if not approval or approval['plan'] != plan_id:
            raise PermissionError('A plan-bound approval token is required')
        preflight(store, plan, approval)
        run_id = uid()
        operations = selected_ops(plan, approval['rows'], run_id, store.home)
        # Every operation is durable BEFORE the first source mutation.
        run = {'id': run_id, 'plan': plan_id, 'root': plan['root'], 'status': 'applying',
               'created': time.time(), 'approval': token, 'error': None}
        for seq, op in enumerate(operations):
            op.update({'seq': seq, 'status': 'prepared'})
            store.op(run_id, seq, op)
        store.put('run', run_id, run)
        approval.update({'used': True, 'run': run_id})
        store.put('approval', token, approval)
        try:
            for seq, op in enumerate(operations):
                op['status'] = 'intent'
                store.op(run_id, seq, op)
                if op['kind'] == 'move':
                    if sha256_file(op['src']) != op['hash']:
                        raise ValueError('Source changed during apply')
                    st = Path(op['src']).stat()
                    op['mtime_ns'], op['atime_ns'] = st.st_mtime_ns, st.st_atime_ns
                    store.op(run_id, seq, op)
                    _move(op['src'], op['dst'])
                else:
                    stage = store.home/'staging'/run_id/str(seq)
                    stage.parent.mkdir(parents=True, exist_ok=True)
                    with stage.open('xb') as handle:
                        handle.write(base64.b64decode(op['content']))
                        handle.flush()
                        os.fsync(handle.fileno())
                    _move(stage, op['dst'])
                op['status'] = 'done'
                store.op(run_id, seq, op)
                if fail_after is not None and seq+1 == fail_after:
                    raise RuntimeError('Injected interruption after durable operation')
            run['status'] = 'applied'
        except BaseException as error:
            run['status'], run['error'] = 'interrupted', str(error)
            raise
        finally:
            store.put('run', run_id, run)
        if run['status'] == 'applied' and approval['source'] == 'human':
            from fis import preference
            preference.applied(store, plan, approval['rows'])
        return run


def rollback_preview(store, run_id, folder=None):
    run = store.get('run', run_id)
    if not run:
        raise ValueError('Unknown run')
    ops = [o for o in store.ops(run_id) if not folder or o['folder'] == folder]
    # Simulate inverse operations to catch all conflicts before touching anything.
    state = {}
    def current(path):
        if path not in state:
            p = Path(path)
            if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
                raise PermissionError('Linked rollback path')
            state[path] = sha256_file(p) if p.is_file() else ('DIRECTORY' if p.exists() else None)
        return state[path]
    conflicts, changes = [], []
    config = gate.policy(store)
    for op in reversed(ops):
        if op['status'] in {'prepared', 'undone'}:
            continue
        for path in [op['dst']] + ([op['src']] if op['kind'] == 'move' else []):
            # Archives are owned state; source targets must still satisfy policy.
            if not gate.under(path, store.home):
                reason = gate.unsafe(path, config)
                if reason:
                    conflicts.append({'path': path, 'why': reason})
        dst = current(op['dst'])
        src = current(op['src']) if op['kind'] == 'move' else None
        quarantine = str(store.home/'quarantine'/run_id/str(op['seq'])/Path(op['dst']).name)
        # Recovery if process died during undo, after a move but before its status commit.
        if op.get('undo_intent') and ((op['kind'] == 'move' and src == op['hash'] and dst is None) or
                                     (op['kind'] == 'write' and dst is None and current(quarantine) == op['hash'])):
            changes.append({**op, 'already_reversed': True})
            continue
        if op['status'] == 'intent' and dst is None and (op['kind'] == 'write' or src == op['hash']):
            continue  # apply did not reach this mutation
        if dst != op['hash']:
            conflicts.append({'path': op['dst'], 'why': 'changed or missing since apply', 'expected': op['hash'], 'actual': dst})
        elif op['kind'] == 'move' and src is not None:
            conflicts.append({'path': op['src'], 'why': 'original path is occupied'})
        else:
            state[op['dst']] = None
            if op['kind'] == 'move':
                state[op['src']] = op['hash']
            changes.append(op)
    return {'run': run_id, 'folder': folder, 'changes': changes, 'conflicts': conflicts}


def undo(store, run_id, folder=None):
    with store.lock():
        preview = rollback_preview(store, run_id, folder)
        if preview['conflicts']:
            store.put('conflict', run_id, preview)
            return preview
        for op in preview['changes']:
            op['undo_intent'] = True
            store.op(run_id, op['seq'], op)
            if not op.get('already_reversed'):
                if op['kind'] == 'move':
                    _move(op['dst'], op['src'])
                    if 'mtime_ns' in op:
                        os.utime(op['src'], ns=(op['atime_ns'], op['mtime_ns']))
                else:
                    dst = store.home/'quarantine'/run_id/str(op['seq'])/Path(op['dst']).name
                    _move(op['dst'], dst)
            op['status'] = 'undone'
            store.op(run_id, op['seq'], op)
        run = store.get('run', run_id)
        run['status'] = 'undone' if all(o['status'] in {'undone', 'prepared', 'intent'} for o in store.ops(run_id)) else 'partially-undone'
        store.put('run', run_id, run)
        return preview
