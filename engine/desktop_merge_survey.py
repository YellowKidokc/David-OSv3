"""Checkpointed metadata survey for supervised Desktop merge review.

Does not modify sources or run merges. Generated/dependency directories are
explicitly excluded and make their containing roots ineligible for full merge.
"""
from __future__ import annotations
import collections
import itertools
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

EXCLUDED = {'$recycle.bin', '#recycle', 'system volume information', '.git',
            'node_modules', '__pycache__', '.venv', 'venv', '.cache'}

def name_key(name):
    return re.sub(r'[^a-z0-9]', '', re.sub(r'\s*\(\d+\)$', '', name.lower()))

def survey(root):
    data = {'root':str(root), 'files':{}, 'directories':[], 'errors':[], 'excluded':[], 'bytes':0}
    pending=[root]
    last=time.monotonic()
    while pending:
        base=pending.pop()
        try:
            with os.scandir(base) as entries:
                for e in entries:
                    rel=Path(e.path).relative_to(root).as_posix()
                    try:
                        s=e.stat(follow_symlinks=False)
                        if e.is_symlink() or getattr(s,'st_file_attributes',0)&0x400:
                            data['errors'].append({'path':rel,'reason':'link/reparse point not followed'})
                        elif stat.S_ISDIR(s.st_mode):
                            if e.name.lower() in EXCLUDED:
                                data['excluded'].append(rel)
                            else:
                                data['directories'].append(rel);pending.append(Path(e.path))
                        elif stat.S_ISREG(s.st_mode):
                            data['files'][rel]={'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
                            data['bytes']+=s.st_size
                        else:
                            data['errors'].append({'path':rel,'reason':'unsupported object'})
                    except OSError as exc:
                        data['errors'].append({'path':rel,'reason':str(exc)})
                    if time.monotonic()-last>15:
                        print(f"  {root.name}: {len(data['files'])} files, {data['bytes']/1e9:.2f} GB",flush=True)
                        last=time.monotonic()
        except OSError as exc:
            data['errors'].append({'path':str(base),'reason':str(exc)})
    return data

def run(recipe):
    out=Path(recipe['output']);out.mkdir(parents=True,exist_ok=True)
    snapshots=out/'metadata';snapshots.mkdir(exist_ok=True)
    records=[]
    for n,path in enumerate(recipe['roots']):
        root=Path(path);file=snapshots/f'{n:04d}.json'
        if file.exists():
            data=json.loads(file.read_text(encoding='utf-8'))
            if data['root']!=str(root):raise ValueError('Checkpoint scope mismatch')
        else:
            print(f"[{n+1}/{len(recipe['roots'])}] {root}",flush=True)
            data=survey(root)
            file.write_text(json.dumps(data),encoding='utf-8')
        records.append(data)
        (out/'progress.json').write_text(json.dumps({'completed_roots':n+1,'total_roots':len(recipe['roots']),
            'files':sum(len(r['files']) for r in records),'logical_bytes':sum(r['bytes'] for r in records)}),encoding='utf-8')
    byname=collections.defaultdict(list)
    for n,r in enumerate(records):byname[name_key(Path(r['root']).name)].append(n)
    pairs={tuple(sorted((a,b))):{'reason':'normalized_name'} for ids in byname.values() for a,b in itertools.combinations(ids,2)}
    # Discover different-name peers from discriminative relative-path/size tokens.
    index=collections.defaultdict(set)
    generic={'readme.md','license','license.txt','package.json','package-lock.json','requirements.txt','desktop.ini','.ds_store'}
    for n,r in enumerate(records):
        for rel,info in r['files'].items():
            if info['bytes'] and Path(rel).name.lower() not in generic:
                index[(rel.lower(),info['bytes'])].add(n)
    overlap=collections.Counter()
    totals=collections.Counter()
    for ids in index.values():
        if len(ids)>15:continue
        for n in ids:totals[n]+=1
        for pair in itertools.combinations(sorted(ids),2):overlap[pair]+=1
    for pair,count in overlap.items():
        ratio=count/min(totals[pair[0]],totals[pair[1]])
        if count>=5 and ratio>=.6:
            pairs.setdefault(pair,{'reason':'relative_path_size_overlap'})
            pairs[pair].update(shared_path_size_tokens=count,metadata_containment=ratio)
    candidates=[{'a':a,'b':b,'a_root':records[a]['root'],'b_root':records[b]['root'],**why} for (a,b),why in sorted(pairs.items())]
    summary={'scope':recipe,'roots':[{'index':n,'root':r['root'],'files':len(r['files']),'bytes':r['bytes'],
        'errors':r['errors'],'excluded':r['excluded'],'checkpoint':str(snapshots/f'{n:04d}.json')} for n,r in enumerate(records)],
        'candidate_pairs':candidates,'status':'metadata_candidates_only_no_identity_or_merge_claim'}
    (out/'survey.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({'roots':len(records),'candidates':len(candidates),'survey':str(out/'survey.json')}),flush=True)

if __name__=='__main__':run(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
