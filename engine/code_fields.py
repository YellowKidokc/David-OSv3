"""Locked keyword codes; metadata proposals are separate from source renames."""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from pathlib import Path

import yaml

from engine import registry

DEFAULT_CODES=Path('C:/theophysics/tools/KEYWORD_CODES.yaml')
DEFAULT_RULES=Path('C:/theophysics/tools/FILING_RULES.yaml')


class Codebook:
    def __init__(self,path=DEFAULT_CODES,rules_path=DEFAULT_RULES):
        self.path=Path(path)
        raw=self.path.read_text(encoding='utf-8')
        self.data=yaml.safe_load(raw)
        self.rules=yaml.safe_load(Path(rules_path).read_text(encoding='utf-8'))
        if 'R02_no_silent_changes' not in self.rules or 'R01_folder_density' not in self.rules:
            raise ValueError('Required filing rules unavailable')
        for group in ('series','concepts','opposition','status_levels'):
            if not isinstance(self.data.get(group),dict):raise ValueError('Invalid codebook '+group)
        self.concepts=set(self.data['concepts'])
        # The locked YAML explicitly permits this range in concepts.LW's comment.
        if re.search(r'use L1-L10\b',raw):self.concepts.update('L'+str(i) for i in range(1,11))
        self.hash=registry.sha256_file(str(self.path))
        self.rules_hash=registry.sha256_file(str(rules_path))

    def validate(self,values,authority='pipeline'):
        allowed={'series','concepts','opposition','status_level','published','confidence','next_review_due'}
        if set(values)-allowed:raise ValueError('Unsupported metadata fields')
        if values.get('series') is not None and values['series'] not in self.data['series']:raise ValueError('Unknown series code')
        if 'concepts' in values and (not isinstance(values['concepts'],list) or any(c not in self.concepts for c in values['concepts'])):
            raise ValueError('Unknown concept code or invalid concepts list')
        if values.get('opposition') is not None and values['opposition'] not in self.data['opposition']:raise ValueError('Unknown opposition code')
        level=values.get('status_level')
        if level is not None:
            if level not in self.data['status_levels']:raise ValueError('Unknown status level')
            if authority!='David' and level not in {'IN','WK','AP'}:raise ValueError('Pipeline may set IN/WK/AP only; human ruling required')
        if 'published' in values and not (type(values['published']) is bool or values['published'] in ('yes','no')):
            raise ValueError('Published must be yes/no or a boolean')
        if 'confidence' in values and (type(values['confidence']) not in (float,int) or not 0<=values['confidence']<=1):
            raise ValueError('Confidence must be 0..1')
        if values.get('next_review_due') is not None:
            dt.date.fromisoformat(values['next_review_due'])
        return values


def update_codes(db,work_id,values,*,authority='pipeline',codebook=None):
    book=codebook or Codebook()
    book.validate(values,authority)
    with registry.connect(db) as con:
        old=con.execute('SELECT * FROM works WHERE work_id=?',(work_id,)).fetchone()
        if old is None:raise ValueError('Unknown work')
        if authority!='David' and old['status_level'] in {'CD','ES','RT'} and 'status_level' in values and values['status_level']!=old['status_level']:
            raise ValueError('Pipeline cannot overwrite a human-ruled level')
        transformed=dict(values)
        if 'concepts' in transformed:transformed['concepts']=registry.dump(transformed['concepts'])
        if 'published' in transformed:transformed['published']=int(transformed['published'] is True or transformed['published']=='yes')
        transformed['code_fields_provenance_json']=registry.dump({'authority':authority,'codebook':str(book.path),'sha256':book.hash,'rules_sha256':book.rules_hash,'at':registry.now()})
        con.execute('UPDATE works SET '+','.join(f'{k}=?' for k in transformed)+' WHERE work_id=?',(*transformed.values(),work_id))
        registry.log(con,uuid.uuid4().hex,'work_codes_updated',work_id,{'fields':values,'authority':authority,'codebook_sha256':book.hash})


def downstream_dependents(edges):
    """dependsOn is dependent -> prerequisite; return transitive reverse reachability."""
    reverse={}
    for e in edges:
        relation=e.get('rel_type',e.get('type'))
        if relation not in {'dependsOn','DEPENDS_ON'}:continue
        dependent=e.get('from_id',e.get('source'))
        prerequisite=e.get('to_id',e.get('target'))
        if not isinstance(dependent,str) or not isinstance(prerequisite,str):raise ValueError('Invalid dependsOn edge')
        reverse.setdefault(prerequisite,set()).add(dependent)
    result={}
    for source in set(reverse)|{v for group in reverse.values() for v in group}:
        seen=set()
        todo=list(reverse.get(source,()))
        while todo:
            node=todo.pop()
            if node in seen or node==source:continue
            seen.add(node);todo.extend(reverse.get(node,()))
        result[source]=sorted(seen)
    return result


def propose_blast_radius(db,edges):
    derived=downstream_dependents(edges)
    graph_hash=registry.key(edges)
    with registry.connect(db) as con:
        for work in con.execute('SELECT work_id FROM works').fetchall():
            wid=work['work_id']
            # IDs must be explicitly present in the dependency graph. Absence is
            # unknown coverage, not proof of zero downstream dependents.
            keys=[k for k in derived if k==wid or k.endswith(':'+wid)]
            if keys:
                registry.queue(con,uuid.uuid4().hex,'blast_radius',wid,
                               {'downstream_dependents':derived[keys[0]],'graph_sha256':graph_hash,'status':'proposed'})
    return derived
