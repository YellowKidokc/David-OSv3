"""Inspectable template rules; corrections are candidates until confirmed."""
import fnmatch
from collections import Counter
from pathlib import Path
from fis.index import uid

TEMPLATES = [
    {'id': 'fable', 'name': 'Fable', 'description': 'Semantic capsule, health, file evidence and recovery', 'source': 'FIS the onr/FIS.html'},
    {'id': 'vault', 'name': 'Vault intelligence', 'description': 'Research files, tags and folder signals', 'source': 'FIS the onr/fis_vault_intelligence_v3.html'},
    {'id': 'signals', 'name': 'Folder signals', 'description': 'Signals and evidence for mixed collections', 'source': 'FIS the onr/6FIS.html'},
    {'id': 'compact', 'name': 'Compact', 'description': 'Short inventory with evidence on demand', 'source': 'FIS the onr/1FIS.html'},
    {'id': 'recovery', 'name': 'Recovery', 'description': 'History and recovery emphasized', 'source': 'FIS the onr/5FIS.html'},
    {'id': 'classic', 'name': 'Classic', 'description': 'Alternative folder reference layout', 'source': 'FIS the onr/2FIS.html'},
]


def registry(store):
    return store.get('templates', 'main', TEMPLATES)


def rules(store):
    return store.get('template-rules', 'main', [
        {'id': 'documents', 'match': {'dominant_class': 'document'}, 'template': 'vault', 'confidence': .85, 'confirmed': True},
        {'id': 'code', 'match': {'dominant_class': 'code'}, 'template': 'compact', 'confidence': .85, 'confirmed': True},
        {'id': 'images', 'match': {'dominant_class': 'image'}, 'template': 'signals', 'confidence': .85, 'confirmed': True},
    ])


def features(folder, files):
    counts = Counter(r['classification']['class'] for r in files)
    dominant = counts.most_common(1)
    return {'path_pattern': str(Path(folder)), 'dominant_class': dominant[0][0] if dominant else 'empty',
            'dominant_ratio': dominant[0][1]/len(files) if files else 0,
            'tags': sorted({t['tag'] for r in files for t in r['tags']})}


def choose(store, folder, files):
    f = features(folder, files)
    override = store.get('template-choice', str(Path(folder).resolve()))
    if override:
        return {**override, 'confidence': 1, 'why': 'David chose this template for this folder', 'features': f}
    for rule in reversed(rules(store)):
        match = rule.get('match', {})
        ok = all((fnmatch.fnmatchcase(f['path_pattern'].casefold(), v.casefold()) if k == 'path_pattern'
                  else (v in f['tags'] if k == 'tag' else f.get(k) == v)) for k, v in match.items())
        if rule.get('confirmed') and ok and (f['dominant_ratio'] >= .6 or 'path_pattern' in match or match.get('dominant_class') == 'empty'):
            return {'template': rule['template'], 'confidence': rule['confidence'],
                    'why': 'Confirmed rule '+rule['id'], 'rule': rule['id'], 'features': f}
    return {'template': None, 'confidence': 0, 'why': 'No confident rule; choose a template', 'features': f}


def teach(store, folder, template, files, generalize=False):
    if template not in {r['id'] for r in registry(store)}:
        raise ValueError('Unknown template')
    folder = str(Path(folder).resolve())
    store.put('template-choice', folder, {'folder': folder, 'template': template})
    if not generalize:
        return {'template': template, 'folder': folder}
    f = features(folder, files)
    candidate = {'id': uid(), 'template': template,
                 'match': {'dominant_class': f['dominant_class']}, 'confidence': .95, 'confirmed': False,
                 'why': 'Proposed from your correction; only active after confirmation', 'example': folder}
    store.put('candidate-rule', candidate['id'], candidate)
    return candidate


def confirm(store, candidate_id):
    candidate = store.get('candidate-rule', candidate_id)
    if not candidate:
        raise ValueError('Unknown candidate rule')
    candidate['confirmed'] = True
    existing = [r for r in rules(store) if r['id'] != candidate_id]
    store.put('template-rules', 'main', existing+[candidate])
    store.put('candidate-rule', candidate_id, candidate)
    # Readable JSON in owned state is the effective configuration, not hidden weights.
    import json
    path = store.home/'template-rules.json'
    # Versioned, append-only exports avoid overwriting previous rule receipts.
    path = path.with_name('template-rules-'+uid()+'.json')
    with path.open('x', encoding='utf-8') as handle:
        json.dump(existing+[candidate], handle, indent=2)
    return candidate
