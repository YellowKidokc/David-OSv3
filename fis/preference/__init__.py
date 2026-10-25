"""Existing frequency/Markov learners; human feedback is the durable source of truth.

No ML dependency, no imports from engine/, no automatic approval. History exports
retain the existing ensemble's decision format for later optional ML adapters.
"""
import json
import time
from pathlib import Path
from fis.index import digest
from fis.preference.frequency import FrequencyEngine
from fis.preference.markov_engine import MarkovEngine
from fis.preference.features import proposal


def events(store):
    return sorted(store.all('preference-event'), key=lambda e: e['at'])


def ensemble(store):
    frequency, markov = FrequencyEngine(), MarkovEngine()
    for event in events(store):
        for learner in (frequency, markov):
            learner.learn(event['proposal'], event['approved'])
    return frequency, markov


def prediction(learners, row):
    p = proposal(row)
    scores = {e.name: e.predict(p) for e in learners}
    ready = [e for e in learners if e.ready]
    weights = {'frequency': .5, 'markov': .8}
    score = sum(weights[e.name]*scores[e.name] for e in ready)/sum(weights[e.name] for e in ready) if ready else .5
    return {'score': round(score, 4), 'engines': scores, 'ready': bool(ready),
            'why': 'Learned from your explicit rename decisions; advisory only', 'auto_approval': False}


def record(store, plan, row, approved, note='', corrected_name=None):
    key = digest([plan['hash'], row['id'], bool(approved), corrected_name or row['target']])
    if store.get('preference-event', key):
        return
    value = {'id': key, 'at': time.time(), 'plan': plan['id'], 'plan_hash': plan['hash'],
             'row': row['id'], 'path': row['path'], 'approved': bool(approved), 'note': note,
             'proposal': proposal(row, corrected_name)}
    store.put('preference-event', key, value)


def applied(store, plan, rows):
    for row in plan['rows']:
        if row['kind'] == 'rename' and row['id'] in rows:
            if row.get('original_target'):
                record(store, plan, {**row, 'target': row['original_target']}, False, 'Corrected by David')
            record(store, plan, row, True, 'Explicitly approved and successfully applied')


def stats(store):
    learners = ensemble(store)
    history = events(store)
    return {'decisions': len(history), 'approved': sum(e['approved'] for e in history),
            'rejected': sum(not e['approved'] for e in history), 'engines': [e.stats() for e in learners],
            'mode': 'blend', 'auto_approval': False}


def export(store):
    return '\n'.join(json.dumps(e, sort_keys=True) for e in events(store))+'\n'
