"""Evidence-bearing v0.4 facets; unrecognized supplied tags remain visible."""
import re
from pathlib import Path

TEXT = (Path(__file__).parent / 'data' / 'TAG_TAXONOMY_v0.4.md').read_text(encoding='utf-8')
VOCABULARY = set(re.findall(r'`((?:ct|rc|ep|wf|tp|ph|th|cs|me|ax|series)-[a-z0-9-]+)`', TEXT))
CONTENT = [('ct-method', r'\b(method|procedure|workflow|how to)\b'),
           ('ct-reference', r'\b(reference|glossary|index)\b'),
           ('ct-outline', r'\boutline\b'), ('ct-status', r'\b(status|progress)\b'),
           ('ct-equation', r'\$\$|\\begin\{equation'),
           ('ct-argument', r'\b(premise|therefore|argument|claim)\b'),
           ('ct-narrative', r'\b(story|narrative)\b')]


def tags(name, text, sidecars='', packs=()):
    evidence = []
    value = name + '\n' + text
    for tag, pattern in CONTENT:
        match = re.search(pattern, value, re.I)
        if match:
            evidence.append({'tag': tag, 'rule': 'taxonomy-v0.4.content', 'source': 'name+sample',
                             'span': list(match.span()), 'quote': match.group(), 'confidence': .7})
            break
    if not evidence:
        evidence.append({'tag': 'ct-source', 'rule': 'taxonomy-v0.4.fallback',
                         'source': 'inventory', 'quote': 'Observed source; role unresolved', 'confidence': .25})
    for tag in sorted(set(re.findall(r'\b(?:ct|rc|ep|wf|tp|ph|th|cs|me|ax|series)-[a-z0-9-]+', text+'\n'+sidecars))):
        if tag.startswith(('tp-', 'th-', 'me-', 'ax-')) and 'theophysics' not in packs:
            continue
        if tag in VOCABULARY and not (tag.startswith('ct-') and evidence):
            evidence.append({'tag': tag, 'rule': 'existing-explicit-tag', 'source': 'content/legacy-sidecar',
                             'quote': tag, 'confidence': .8})
    return evidence
