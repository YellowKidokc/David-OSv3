"""
AI Chat Fat Cutter
Layer 2 of the Chat-to-Vault Pipeline

Takes segmented topic pages and strips non-substance content.
Outputs cleaned pages, error ledger entries, and cut logs.

Usage:
  python chat_fat_cutter.py <input_folder> <output_folder>
"""

import os, sys, re, json
from pathlib import Path
from datetime import datetime

# Patterns to CUT (performative filler, greetings, meta)
CUT_PATTERNS = [
    r"(?i)^that'?s?\s+(?:a\s+)?(?:great|excellent|wonderful|interesting)\s+(?:question|point|observation)",
    r"(?i)^glad\s+you\s+(?:asked|mentioned|brought)",
    r"(?i)^(?:absolutely|definitely|certainly)[.!]?\s*$",
    r"(?i)^(?:i'?d\s+be\s+happy|happy)\s+to\s+help",
    r"(?i)^(?:sure|of course)[,.]?\s*(?:let'?s|i'?ll)",
    r"(?i)^(?:thanks?\s+for\s+sharing|thank\s+you\s+for)",
    r"(?i)^(?:hey|hi|hello|good\s+(?:morning|afternoon|evening))[\s,!.]*$",
    r"(?i)^(?:talk\s+later|bye|goodbye|see\s+you|take\s+care)",
    r"(?i)^(?:sorry\s+(?:about\s+that|for\s+the))",
    r"(?i)^(?:you'?re\s+welcome|no\s+problem|my\s+pleasure)",
]

# Patterns that signal ERROR LEDGER entries (corrections, revisions)
ERROR_PATTERNS = [
    r"(?i)(?:i\s+was\s+wrong|that'?s?\s+(?:not\s+)?(?:right|correct|accurate))",
    r"(?i)(?:actually|correction|let\s+me\s+correct|i\s+(?:need\s+to\s+)?revise)",
    r"(?i)(?:(?:on\s+)?second\s+thought|wait.*?that'?s?\s+not)",
    r"(?i)(?:previous(?:ly)?\s+(?:said|claimed|stated).*?(?:but|however|wrong))",
    r"(?i)(?:supersed(?:ed?|es)|replaced?\s+by|no\s+longer\s+(?:true|valid|correct))",
]

# Patterns to PRESERVE (never cut these even if they match cut patterns)
PRESERVE_PATTERNS = [
    r"(?:equation|formula|theorem|axiom|law\s+\d|derivat|proof|lemma)",
    r"(?:therefore|thus|hence|it\s+follows|QED|∴)",
    r"(?:[A-Z]_\{|\\frac|\\int|\\sum|\\nabla|χ|Φ|ψ|∫|∑|∇)",
    r"(?:sigma|p-value|confidence|correlation|r\s*=|p\s*[<>=])",
    r"(?:scripture|verse|chapter|genesis|exodus|galatians|john|romans|matthew)",
    r"(?:grace|entropy|coherence|negentropy|master\s+equation|lagrangian)",
]


def is_cuttable(line: str) -> bool:
    """Check if a line is performative filler that should be cut."""
    stripped = line.strip()
    if len(stripped) < 5:
        return True  # blank or trivial

    # Never cut lines with preserved content
    for pattern in PRESERVE_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return False

    # Cut if matches any cut pattern
    for pattern in CUT_PATTERNS:
        if re.search(pattern, stripped):
            return True

    return False


def is_error_entry(line: str) -> bool:
    """Check if a line contains a correction/revision worth logging."""
    for pattern in ERROR_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def process_file(input_path: Path, output_dir: Path, error_ledger: list):
    """Process a single segmented topic page."""
    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Split YAML frontmatter from body
    yaml_block = ""
    body = content
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            yaml_block = content[:end+3]
            body = content[end+3:]

    lines = body.split('\n')
    kept = []
    cut_log = []
    errors_found = []

    for i, line in enumerate(lines):
        # Check for error ledger entries FIRST (preserve these)
        if is_error_entry(line):
            errors_found.append({
                'line_number': i,
                'text': line.strip(),
                'source_file': input_path.name,
                'detected_at': datetime.now().isoformat()
            })
            kept.append(line)  # keep corrections in the curated page too
            continue

        if is_cuttable(line):
            if line.strip():  # don't log blank line cuts
                cut_log.append({
                    'line': i,
                    'text': line.strip()[:100],
                    'reason': 'filler_pattern'
                })
        else:
            kept.append(line)

    # Update YAML to mark as curated
    if yaml_block:
        yaml_block = yaml_block.replace('stage: "segmented"', 'stage: "curated"')
        yaml_block = yaml_block.replace('curated: false', 'curated: true')
        if 'curated_at' not in yaml_block:
            yaml_block = yaml_block.replace(
                'curated: true',
                f'curated: true\n  curated_at: "{datetime.now().isoformat()}"'
            )

    # Write curated page
    curated_content = yaml_block + '\n'.join(kept)
    out_path = output_dir / input_path.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(curated_content)

    # Write cut log
    if cut_log:
        log_path = output_dir / (input_path.stem + '_CUTS.json')
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(cut_log, f, indent=2)

    # Add to error ledger
    error_ledger.extend(errors_found)

    stats = {
        'original_lines': len(lines),
        'kept_lines': len(kept),
        'cut_lines': len(lines) - len(kept),
        'errors_found': len(errors_found),
        'cut_pct': round((len(lines) - len(kept)) / max(len(lines), 1) * 100, 1)
    }
    return stats


def process_folder(input_folder: str, output_folder: str):
    """Process all segmented topic pages in a folder tree."""
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    md_files = list(input_path.rglob('*.md'))
    md_files = [f for f in md_files if not f.name.startswith('_')]
    print(f"Found {len(md_files)} topic pages to curate")

    error_ledger = []
    total_stats = {'files': 0, 'original': 0, 'kept': 0, 'cut': 0, 'errors': 0}

    for md_file in md_files:
        # Mirror folder structure
        rel = md_file.relative_to(input_path)
        out_dir = output_path / rel.parent

        stats = process_file(md_file, out_dir, error_ledger)
        total_stats['files'] += 1
        total_stats['original'] += stats['original_lines']
        total_stats['kept'] += stats['kept_lines']
        total_stats['cut'] += stats['cut_lines']
        total_stats['errors'] += stats['errors_found']

        if stats['cut_lines'] > 0:
            print(f"  {rel}: {stats['cut_pct']}% cut ({stats['cut_lines']}/{stats['original_lines']} lines)")

    # Write error ledger
    if error_ledger:
        ledger_path = output_path / '_ERROR_LEDGER.json'
        with open(ledger_path, 'w', encoding='utf-8') as f:
            json.dump(error_ledger, f, indent=2, ensure_ascii=False)
        print(f"\nError ledger: {len(error_ledger)} entries -> {ledger_path}")

    print(f"\n{'='*60}")
    print(f"DONE: {total_stats['files']} files processed")
    print(f"  Original: {total_stats['original']} lines")
    print(f"  Kept:     {total_stats['kept']} lines")
    print(f"  Cut:      {total_stats['cut']} lines ({round(total_stats['cut']/max(total_stats['original'],1)*100,1)}%)")
    print(f"  Errors:   {total_stats['errors']} corrections logged")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python chat_fat_cutter.py <input_folder> <output_folder>")
        sys.exit(1)
    process_folder(sys.argv[1], sys.argv[2])
