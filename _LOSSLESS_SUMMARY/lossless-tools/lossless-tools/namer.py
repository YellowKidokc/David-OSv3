"""
namer.py — Theophysics File Naming System
Generates LOSS__ and MEQ__ internal names for vial files.
Reads a markdown/text file, detects type, writes the internal name as H1 header line 1.

Usage:
    python namer.py <file>              # auto-detect general vs MEQ
    python namer.py <file> --mode meq   # force MEQ naming
    python namer.py <file> --mode loss  # force general naming
"""

import sys
import re
import os
from datetime import date


MEQ_KEYWORDS = re.compile(
    r'\b(master[\s_-]*equation|nabla|meq|master[\s_-]*eq|chi[\s_-]*field|lagrangian|coherence[\s_-]*equation)\b',
    re.IGNORECASE,
)


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r'[^\w]+', '_', text).strip('_')
    if not slug:
        return 'file'
    return slug[:max_len].rstrip('_')


def get_title(path: str) -> str:
    """Pull the first heading or first non-blank line as a title."""
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.match(r'^#+\s+(.+)$', line)
                if m:
                    return m.group(1).strip()
                return line
    except Exception:
        pass
    return name


def detect_mode(path: str) -> str:
    """Scan first 100 lines for MEQ keywords."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                if i > 100:
                    break
                if MEQ_KEYWORDS.search(line):
                    return 'meq'
    except Exception:
        pass
    return 'loss'


def source_date(path: str) -> str:
    """Return the source file's modified date as YYYY-MM-DD."""
    try:
        from datetime import datetime
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
    except Exception:
        return date.today().isoformat()


def build_internal_name(slug: str, mode: str, file_date: str = None) -> str:
    prefix = 'MEQ' if mode == 'meq' else 'LOSS'
    d = file_date or date.today().isoformat()
    return f'{prefix}__{slug}__{d}'


def apply_name(path: str, internal_name: str) -> None:
    """Write the internal name as H1 on line 1. If line 1 is already a
    LOSS__ or MEQ__ header, replace it. Otherwise prepend."""
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    header = f'# {internal_name}\n'

    if lines and re.match(r'^#\s+(LOSS__|MEQ__)', lines[0]):
        lines[0] = header
    else:
        lines.insert(0, header + '\n')

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f'Named: {internal_name}')
    print(f'File:  {path}')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f'Error: {path} not found')
        sys.exit(1)

    mode = None
    if '--mode' in sys.argv:
        idx = sys.argv.index('--mode')
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1].lower()

    if mode not in ('loss', 'meq'):
        mode = detect_mode(path)

    title = get_title(path)
    slug = slugify(title)
    internal_name = build_internal_name(slug, mode)
    apply_name(path, internal_name)


if __name__ == '__main__':
    main()
