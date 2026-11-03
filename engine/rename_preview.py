"""R01/R02 pilot filing preview. Produces reports only; no apply command."""
from __future__ import annotations
import argparse
import csv
import io
import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

from engine import registry
from engine.code_fields import Codebook


def terms(value):
    return re.findall(r'[a-z0-9]+',value.casefold())


def score_codes(mapping,title,body):
    title_text=' '+' '.join(terms(title))+' '; body_text=' '+' '.join(terms(body))+' '
    scored=[]
    for code,label in mapping.items():
        # Match complete label phrases, not words such as modal "will" from
        # "Free Will" or generic "problem" from "Problem of evil".
        cues=[' '.join(terms(part)) for part in str(label).split('/')]
        if code.startswith('x') and len(terms(label))>1 and terms(label)[0] not in {'problem','is'}:
            cues.append(terms(label)[0])
        title_hits=sum((' '+cue+' ') in title_text for cue in cues if cue)
        hits=sum(body_text.count(' '+cue+' ') for cue in cues if cue)
        if title_hits or hits:
            scored.append((title_hits*20+math.log2(hits+1),code,{'title_cues':[w for w in cues if (' '+w+' ') in title_text],'body_phrase_hits':hits}))
    return sorted(scored,key=lambda x:(-x[0],x[1]))


def filename(title,ext,series,number,concepts,opposition,book):
    book.validate({'series':series,'concepts':concepts,'opposition':opposition})
    if not 1<=len(concepts)<=2:raise ValueError('Filename requires one or two concepts')
    if series and not re.fullmatch(r'\d{1,3}[A-Z]?',number or ''):raise ValueError('Series ordinal missing or invalid')
    clean=unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode().lower()
    words=[w for w in re.findall(r'[a-z0-9]+',clean) if w not in {'the','of','and','a','an','book','zero','ii','iii','iv','v','vi','vii','viii','ix'}]
    slug='_'.join(words[:4]) or 'document'
    prefix=f'{series}-{number}' if series else concepts[0]
    remaining=concepts if series else concepts[1:]
    parts=[prefix,slug]
    if remaining:parts.append('-'.join(remaining))
    if opposition:parts.append(opposition)
    return '_'.join(parts)+ext


def real_item(path,record_types):
    low=path.name.casefold()
    if record_types.get(str(path)) in {'infrastructure','index'}:return False
    if low in {'fis.html','fis.md','.fisnote','.fis','sidecars','sidecars_and_json','dossiers','thumbnails'}:return False
    if low.endswith(('.fisnote','.fmeta','.bak','.sidecar.json','.canon.sidecar.json')):return False
    if low.startswith(('.fisnote.legacy.','thumbnail','thumb_')):return False
    return True


def build(db,root,output,codebook=None):
    book=codebook or Codebook();root=Path(root).resolve(strict=True);output=Path(output).resolve()
    if output.is_relative_to(root):raise ValueError('Preview output must be outside the pilot')
    with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True) as con:
        con.row_factory=sqlite3.Row
        rows=[dict(r) for r in con.execute('''SELECT f.*,v.work_id,w.preferred_title,w.record_type,w.paper_number,w.series_code,w.series,w.concepts,w.opposition
            FROM files f JOIN versions v ON v.version_id=f.version_id JOIN works w ON w.work_id=v.work_id WHERE f.present=1 ORDER BY f.path''')
            if Path(r['path']).is_relative_to(root)]
    proposals=[]
    for row in rows:
        path=Path(row['path']);reason=[];proposed='';used={};confidence=None
        if row['record_type']!='work':reason=['Held: '+row['record_type']+' record; no source rename proposed']
        else:
            if registry.sha256_file(str(path))!=row['sha256']:raise ValueError('Source changed since scan: '+str(path))
            body,readable,error,method=registry.extract(path)
            if readable!='yes':reason=['Held: no readable source text']
            else:
                scores=score_codes(book.data['concepts'],row['preferred_title'],body)
                stored_concepts=json.loads(row['concepts'])
                book.validate({'concepts':stored_concepts})
                concepts=stored_concepts or [r[1] for r in scores[:2]]
                concepts=concepts[:2]
                opposition_scores=score_codes(book.data['opposition'],row['preferred_title'],body)
                opposition=row['opposition'] or (opposition_scores[0][1] if opposition_scores else None)
                # A root-derived series alone does not prove membership. Preserve
                # observed book ordinals; unnumbered papers receive one-off previews.
                series=(row['series'] or row['series_code']) if row['paper_number'] else None
                if concepts:
                    proposed=filename(row['preferred_title'],path.suffix,series,row['paper_number'],concepts,opposition,book)
                    used={'series':series,'concepts':concepts,'opposition':opposition}
                    confidence=min(.75,.25+.02*scores[0][0]) if scores else None
                    reason=['PROPOSAL ONLY; keyword cues do not establish classification or opposition',
                            'concept evidence: '+registry.dump(scores[:2])]
                    if opposition:reason.append('opposition cue requires David review: '+registry.dump(opposition_scores[:1]))
                    if series:reason.append('existing series/ordinal used; membership remains subject to review')
                else:reason=['Held: no concept code supported by the locked vocabulary cues']
        if proposed and path.with_name(proposed).exists() and path.with_name(proposed)!=path:reason.append('HOLD: target already exists')
        proposals.append({'old_path':str(path),'proposed_name':proposed,'codes_used':registry.dump(used),'reason':'; '.join(reason),
                          'confidence':confidence,'source_sha256':row['sha256'],'codebook_sha256':book.hash})
    counts={}
    for row in proposals:
        if row['proposed_name']:counts[row['proposed_name'].casefold()]=counts.get(row['proposed_name'].casefold(),0)+1
    for row in proposals:
        if counts.get(row['proposed_name'].casefold(),0)>1:row['reason']+='; HOLD: proposed filename collision'
    types={r['path']:r['record_type'] for r in rows};density=[];misspellings=[]
    for here,dirs,names in __import__('os').walk(root,followlinks=False):
        folder=Path(here)
        dirs[:]=[d for d in dirs if not (folder/d).is_symlink() and not getattr(folder/d,'is_junction',lambda:False)()]
        entries=[folder/n for n in dirs+names]
        for path in entries:
            if 'theopyhiscs' in path.name.casefold():misspellings.append(str(path))
        real=[p for p in entries if real_item(p,types)]
        exempt=folder.name.casefold() in {str(v).casefold() for v in book.data['series'].values()}|{k.casefold() for k in book.data['series']}
        action='exempt-series-folder' if exempt else 'propose-remove-empty-after-note-log' if not real else 'propose-flatten-after-note-transfer' if len(real)==1 else 'flag-over-10-no-auto-split' if len(real)>10 else 'retain'
        moves=[{'old_path':str(p),'proposed_path':str(folder.parent/p.name),'collision':(folder.parent/p.name).exists()} for p in real] if len(real)==1 and not exempt else []
        density.append({'folder':str(folder),'real_items':len(real),'proposal':action,'old_to_new':registry.dump(moves),
                        'excluded_notes':registry.dump([str(p) for p in entries if p not in real]),'applied':False})
    if 'theopyhiscs' in root.name.casefold():misspellings.append(str(root))
    output.mkdir(parents=True,exist_ok=True)
    for name,data in [('rename_proposals.csv',proposals),('folder_density.csv',density)]:
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(data[0]) if data else ['old_path','proposed_name','codes_used','reason'])
        writer.writeheader();writer.writerows(data);registry.write_if_changed(output/name,stream.getvalue())
    report=['# Pilot renamer — DRY RUN ONLY','','R02: no files renamed, moved, removed, or rewritten. All keyword classifications require David review.',
            '',f'{len(proposals)} file rows; {sum(bool(r["proposed_name"]) for r in proposals)} filename proposals.',
            '', '## Names containing "theopyhiscs"','',*(misspellings or ['None found within the accepted pilot scope.']),
            '', '## R01 folders with zero or one real item','']
    report += [f"- {r['folder']}: {r['real_items']} real item(s); {r['proposal']}; {r['old_to_new']}" for r in density if r['real_items']<=1] or ['None found within the accepted pilot scope.']
    report += ['', '## Over-ten / series exemptions','']+[f"- {r['folder']}: {r['real_items']} real items; {r['proposal']}" for r in density if r['real_items']>10 or r['proposal']=='exempt-series-folder']
    registry.write_if_changed(output/'REVIEW.md','\n'.join(report)+'\n')
    receipt={'source_mutations':False,'files':len(rows),'proposals':sum(bool(r['proposed_name']) for r in proposals),
             'misspellings':misspellings,'density':density,'codebook_sha256':book.hash,'rules_sha256':book.rules_hash}
    registry.write_if_changed(output/'receipt.json',registry.dump(receipt))
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,default=registry.REPO/'_data/registry.sqlite');p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();print(registry.dump(build(args.db,args.root,args.output)))
