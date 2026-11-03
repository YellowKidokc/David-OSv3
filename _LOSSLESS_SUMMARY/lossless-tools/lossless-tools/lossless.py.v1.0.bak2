"""
lossless.py — Lossless Vial Pipeline
Watches inbox/, compresses each file via DeepSeek, names it, writes to outbox/, moves original to done/.

Usage:
    python lossless.py                  # process all files in inbox/
    python lossless.py --watch          # watch inbox/ and process new files
    python lossless.py somefile.md      # process a single file directly
"""

import sys
import os
import time
import shutil
import re
from datetime import date

# Import sibling scripts
from namer import slugify, get_title, detect_mode, build_internal_name
from deepseek_call import call_deepseek

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(SCRIPT_DIR, 'inbox')
OUTBOX = os.path.join(SCRIPT_DIR, 'outbox')
DONE = os.path.join(SCRIPT_DIR, 'done')

SUPPORTED_EXT = {'.md', '.txt', '.html', '.htm'}


def ensure_dirs():
    for d in (INBOX, OUTBOX, DONE):
        os.makedirs(d, exist_ok=True)


def process_file(path: str) -> str | None:
    """Compress one file. Returns output path or None on failure."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXT:
        print(f'  Skip (unsupported): {os.path.basename(path)}')
        return None

    print(f'  Reading: {os.path.basename(path)}')
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    if len(content.strip()) < 20:
        print(f'  Skip (too short): {os.path.basename(path)}')
        return None

    mode = detect_mode(path)
    title = get_title(path)
    slug = slugify(title)
    internal_name = build_internal_name(slug, mode)

    print(f'  Mode: {mode} | Name: {internal_name}')
    print(f'  Calling DeepSeek...')

    try:
        vial_text = call_deepseek(content, mode)
    except SystemExit:
        print(f'  ERROR: DeepSeek call failed for {os.path.basename(path)}')
        return None

    # Ensure the vial starts with the right H1 header
    header = f'# {internal_name}'
    if not vial_text.startswith('#'):
        vial_text = header + '\n\n' + vial_text
    else:
        # Replace whatever header DeepSeek put with our canonical one
        vial_text = re.sub(r'^#[^\n]*', header, vial_text, count=1)

    # Write to outbox
    out_name = os.path.splitext(os.path.basename(path))[0] + '.vial.md'
    out_path = os.path.join(OUTBOX, out_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(vial_text)

    print(f'  Output: {out_name}')
    return out_path


def process_inbox():
    """Process all files in inbox/, move originals to done/."""
    ensure_dirs()
    files = [f for f in os.listdir(INBOX)
             if os.path.isfile(os.path.join(INBOX, f))
             and not f.startswith('.')]

    if not files:
        print('Inbox empty.')
        return

    print(f'Found {len(files)} file(s) in inbox/')
    for fname in sorted(files):
        src = os.path.join(INBOX, fname)
        result = process_file(src)
        if result:
            dest = os.path.join(DONE, fname)
            if os.path.exists(dest):
                base, ext = os.path.splitext(fname)
                dest = os.path.join(DONE, f'{base}_{date.today().isoformat()}{ext}')
            shutil.move(src, dest)
            print(f'  Moved original → done/{os.path.basename(dest)}')
        print()

    print('Done.')


def watch_inbox(interval: int = 5):
    """Poll inbox/ every N seconds for new files."""
    ensure_dirs()
    print(f'Watching inbox/ (every {interval}s). Ctrl+C to stop.')
    seen = set()
    try:
        while True:
            files = set(os.listdir(INBOX)) - seen
            new_files = [f for f in files
                         if os.path.isfile(os.path.join(INBOX, f))
                         and not f.startswith('.')]
            for fname in sorted(new_files):
                src = os.path.join(INBOX, fname)
                result = process_file(src)
                if result:
                    dest = os.path.join(DONE, fname)
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(fname)
                        dest = os.path.join(DONE, f'{base}_{date.today().isoformat()}{ext}')
                    shutil.move(src, dest)
                    print(f'  Moved original → done/{os.path.basename(dest)}')
                seen.add(fname)
                print()
            time.sleep(interval)
    except KeyboardInterrupt:
        print('\nStopped.')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--watch':
        watch_inbox()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        # Single file mode
        ensure_dirs()
        path = sys.argv[1]
        if not os.path.isfile(path):
            print(f'Error: {path} not found')
            sys.exit(1)
        result = process_file(path)
        if result:
            print(f'\nVial written to: {result}')
    else:
        process_inbox()


if __name__ == '__main__':
    main()
