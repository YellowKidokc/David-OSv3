"""Conservative class assignments; no authority inferred from filenames."""
from pathlib import Path


def classify(path, tags):
    ext = Path(path).suffix.lower()
    groups = {'code': {'.py', '.js', '.ts', '.rs', '.lean', '.ps1', '.bat'},
              'document': {'.md', '.txt', '.rst', '.html', '.htm', '.pdf', '.docx'},
              'data': {'.json', '.csv', '.tsv', '.sqlite', '.db', '.xlsx'},
              'image': {'.png', '.jpg', '.jpeg', '.webp', '.svg'},
              'audio': {'.mp3', '.wav', '.flac'}, 'video': {'.mp4', '.mkv', '.webm'}}
    kind = next((k for k, v in groups.items() if ext in v), 'UNKNOWN')
    return {'class': kind, 'confidence': .9 if kind != 'UNKNOWN' else 0,
            'standing': 'unresolved', 'why': [{'rule': 'extension-class', 'evidence': ext}],
            'content_type': tags[0]['tag']}
