"""Apply an explicitly reviewed merge receipt; retire extras by same-share rename.

No discovery, recursive deletion, overwrites, or scheduling. Every source must
match its reviewed snapshot. Recovery and keeper remain available after success.
"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

from engine.folder_merge import inventory
from engine.fingerprint import sha256_file
from engine.path_write_policy import require_write_allowed


def same_snapshot(a, b):
    return (not a['errors'] and not b['errors'] and a['files']==b['files']
            and sorted(a['directories'])==sorted(b['directories']))


def apply_reviewed(receipt: dict, snapshots: dict, source_scope: Path,
                   recovery: Path, *, approved=False, reference_hits=None,
                   journal: Path) -> dict:
    result={'label':receipt['review']['label'],'status':'held','recovered':[],
            'added_files':[], 'errors':[], 'keeper':receipt['selected_largest']}
    def record(event, **details):
        entry={'utc':datetime.now(timezone.utc).isoformat(),'label':result['label'],
               'event':event,**details}
        journal.parent.mkdir(parents=True,exist_ok=True)
        with journal.open('a',encoding='utf-8') as f:
            f.write(json.dumps(entry,ensure_ascii=False)+'\n');f.flush()
    def hold(reason):
        result['errors'].append(reason);record('held',reason=reason)
        return result
    if not approved or not receipt.get('verified'):
        return hold('Explicit scope approval and verified reviewed receipt required')
    if reference_hits:
        return hold('Known reference or running-process dependency: '+json.dumps(reference_hits))
    roots=[Path(p).resolve(strict=True) for p in receipt['review']['roots']]
    keeper=Path(receipt['selected_largest']).resolve(strict=True)
    stage=Path(receipt['destination']).resolve(strict=True)
    scope=source_scope.resolve(strict=True)
    recovery=recovery.resolve()
    if keeper not in roots or len(set(roots))!=len(roots) or len(roots)<2:
        return hold('Invalid reviewed root set')
    for path in roots:
        if scope not in path.parents:
            return hold('Source outside explicit scope: '+str(path))
        require_write_allowed(path)
        if path==stage or path in stage.parents or stage in path.parents:
            return hold('Staging and originals overlap')
        if path==recovery or path in recovery.parents or recovery in path.parents:
            return hold('Recovery and originals overlap')
    require_write_allowed(recovery)
    expected={}
    for op in receipt['operations']:
        target=Path(op['target']).resolve()
        if stage not in target.parents:
            return hold('Receipt target escapes staging')
        rel=target.relative_to(stage).as_posix()
        if rel in expected and expected[rel]!=op['sha256']:
            return hold('Conflicting receipt mapping')
        expected[rel]=op['sha256']
    live_stage=inventory(stage,workers=4)
    if live_stage['errors'] or {p:v['sha256'] for p,v in live_stage['files'].items()}!=expected:
        return hold('Staging differs from verified receipt')
    for path in roots:
        baseline=snapshots.get(str(path))
        if baseline is None or not same_snapshot(baseline,inventory(path,workers=4)):
            return hold('Source changed or incomplete since review: '+str(path))
    # Validate all live destination collisions before creating anything.
    for rel,digest in expected.items():
        target=keeper/rel
        if target.exists() and (not target.is_file() or sha256_file(str(target))!=digest):
            return hold('Keeper target differs from reviewed plan: '+str(target))
    record('prepared',keeper=str(keeper),roots=list(map(str,roots)),recovery=str(recovery))
    try:
        for directory in live_stage['directories']:
            (keeper/directory).mkdir(parents=True,exist_ok=True)
        for rel,digest in expected.items():
            source,target=stage/rel,keeper/rel
            if target.exists():continue
            record('copy_planned',source=str(source),target=str(target),sha256=digest)
            target.parent.mkdir(parents=True,exist_ok=True)
            with source.open('rb') as inp,target.open('xb') as out:
                shutil.copyfileobj(inp,out,1024*1024)
            shutil.copystat(source,target)
            if sha256_file(str(target))!=digest:
                raise OSError('New copy failed verification: '+str(target))
            result['added_files'].append(str(target));record('copied',target=str(target),sha256=digest)
        live_keeper=inventory(keeper,workers=4)
        if live_keeper['errors'] or any(live_keeper['files'].get(p,{}).get('sha256')!=h for p,h in expected.items()):
            raise OSError('Keeper does not contain complete verified merge')
        if not set(live_stage['directories']).issubset(live_keeper['directories']):
            raise OSError('Keeper missing an expected directory')
        recovery.mkdir(parents=True,exist_ok=False)
        for n,path in enumerate(roots):
            if path==keeper:continue
            if not same_snapshot(snapshots[str(path)],inventory(path,workers=4)):
                raise OSError('Source changed before retirement: '+str(path))
            target=recovery/f'{n:02d}_{path.name}'
            if target.exists():raise FileExistsError(target)
            # Resolve and check both absolute paths immediately before rename.
            path=path.resolve(strict=True);target=target.resolve()
            if scope not in path.parents or recovery not in target.parents:
                raise ValueError('Retirement path escaped checked scope')
            record('retirement_planned',source=str(path),target=str(target))
            path.rename(target)
            if not same_snapshot(snapshots[str(path)],inventory(target,workers=4)):
                if not path.exists():
                    target.rename(path);record('restored_after_verification_failure',source=str(path))
                raise OSError('Recovery verification failed: '+str(target))
            result['recovered'].append({'original':str(path),'recovery':str(target)})
            record('retired',source=str(path),target=str(target))
        # Recheck retained contents after retiring extras.
        after=inventory(keeper,workers=4)
        if after['errors'] or any(after['files'].get(p,{}).get('sha256')!=h for p,h in expected.items()):
            raise OSError('Post-retirement keeper verification failed; use recovery receipt')
        result['status']='complete';record('complete',**result)
    except (OSError,ValueError) as exc:
        result['status']='needs_review';result['errors'].append(str(exc));record('needs_review',**result)
    return result
