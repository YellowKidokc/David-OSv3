"""Portable path policy and preserved rule stack; approval is a separate authority."""
import json
import os
from pathlib import Path
from fis.gate_rules import Gate, SECRET_NAMES, SECRET_SUFFIXES

DATA = Path(__file__).parent / "data"
SKIP = {'.git', '.venv', 'venv', 'node_modules', 'target', '__pycache__', '.obsidian',
        '$recycle.bin', 'system volume information', 'zzz_delete', '.fis'}


def under(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def defaults():
    return {'roots': [], 'protected': [], 'skip': [], 'rulepacks': [], 'provider': 'off',
            'speed': 'Background', 'idle_boost': False, 'html_roots': [], 'profiles': []}


def policy(store):
    config = store.get('config', 'main', defaults())
    if not isinstance(config, dict):
        raise ValueError('Malformed policy: mutations blocked')
    for name in ('roots', 'protected', 'skip', 'rulepacks', 'html_roots', 'profiles'):
        if not isinstance(config.get(name), list):
            raise ValueError('Malformed policy field: ' + name)
    if config.get('provider') != 'off':
        raise ValueError('No provider enabled in this offline distribution')
    return config


def unsafe(path, config):
    p = Path(path)
    resolved = p.resolve()
    # Reject reparse points anywhere in a path, including Windows junctions.
    for part in (p, *p.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            return 'symbolic link or junction'
    if any(x.casefold() in SKIP | {str(s).casefold() for s in config.get('skip', [])} for x in p.parts):
        return 'excluded directory'
    if (p.name.lower() in SECRET_NAMES or p.name.lower().endswith(SECRET_SUFFIXES)
        or p.name.lower().startswith('.env.') or any(s in p.name.lower() for s in ('api_key', 'apikey', 'secret', 'token'))):
        return 'secret file'
    if any(under(resolved, x) for x in config.get('protected', [])):
        return 'protected root'
    # Match actual path boundaries, not prefixes such as /binary or C:\\WindowsNotes.
    systems = [Path(os.environ.get('SystemRoot', 'C:/Windows')),
               Path('C:/Program Files'), Path('C:/Program Files (x86)')]
    if os.name != 'nt':
        systems += [Path('/etc'), Path('/usr'), Path('/bin'), Path('/sbin')]
    if any(under(resolved, x) for x in systems):
        return 'system root'
    return ''


def check(store, root, paths, action='rename'):
    config = policy(store)
    root = Path(root).resolve()
    if not any(under(root, x) for x in config['roots']):
        raise PermissionError('Root has not been explicitly authorized')
    if under(store.home, root) or under(root, store.home):
        raise PermissionError('State/archive and source trees must be separate')
    for path in [root, *map(Path, paths)]:
        reason = unsafe(path, config)
        if reason:
            raise PermissionError(f'{path}: {reason}')
        if not under(path, root):
            raise PermissionError('Path escapes selected root')
    profile = {'approval_floor': 'approval_required'}
    for item in config['profiles']:
        if not isinstance(item, dict) or 'root' not in item or 'approval_floor' not in item:
            raise ValueError('Malformed profile; fail closed')
        if under(root, item['root']):
            profile = item
    floor = profile.get('approval_floor')
    if floor not in {'approval_required', 'blocked', 'preview_only', 'suggest_only', 'auto_after_threshold'}:
        raise ValueError('Unknown approval floor; fail closed')
    if floor in {'blocked', 'preview_only', 'suggest_only'}:
        raise PermissionError('Folder policy is ' + floor)
    gate = Gate.load(DATA, profile)
    if gate.load_error:
        raise PermissionError(gate.load_error)
    verdict = gate.evaluate(action, [str(p) for p in paths])
    if verdict.verdict in {'block', 'drop', 'preview'}:
        raise PermissionError(json.dumps(verdict.to_json()))
    return config
