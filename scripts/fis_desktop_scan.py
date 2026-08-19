#!/usr/bin/env python3
r"""Run the FIS folder-memory scanner across a desktop tree.

Default target:
    H:\Desktop

Writes:
    H:\Desktop\FIS.html
    H:\Desktop\.fis\fis_index.sqlite
    one generated FIS.html per folder
    one generated .fisnote per folder and per file

The imported scanner is inventory-only: it records, renders, and cleans up only
generated stale file-note sidecars. It does not move, rename, delete source
files, or promote canon status.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIS_SYSTEM = REPO_ROOT / "file-intelligence-system"
sys.path.insert(0, str(FIS_SYSTEM))

from fis_folder_memory import scan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build desktop-wide FIS HTML, sidecars, and SQLite index.")
    parser.add_argument("--root", type=Path, default=Path(r"H:\Desktop"), help="Desktop root to scan")
    parser.add_argument("--db", type=Path, help="SQLite index path; default is <root>\\.fis\\fis_index.sqlite")
    parser.add_argument("--ai-limit", type=int, default=0, help="Local Ollama enrichment limit; default disables AI")
    parser.add_argument("--local-ai", action="store_true", help="Enable local Ollama retrieval enrichment")
    parser.add_argument("--no-folder-notes", action="store_true", help="Do not write generated folder .fisnote views")
    parser.add_argument("--no-file-notes", action="store_true", help="Do not write generated per-file .fisnote sidecars")
    parser.add_argument("--no-html", action="store_true", help="Do not write FIS.html pages and dossiers")
    parser.add_argument("--no-cleanup-stale", action="store_true", help="Do not remove stale generated per-file sidecars")
    parser.add_argument("--no-wipe-fisnotes", action="store_true", help="Do not delete existing .fisnote files before scanning")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")
    db_path = (args.db or (root / ".fis" / "fis_index.sqlite")).resolve()

    folders, files, enriched, failed, notes, note_skips, stale, wiped = scan(
        root=root,
        db_path=db_path,
        recursive=True,
        write=not args.no_folder_notes,
        html=not args.no_html,
        local_ai=args.local_ai,
        ai_limit=args.ai_limit,
        ai_model="qwen3:4b-instruct",
        file_notes=not args.no_file_notes,
        cleanup_stale=not args.no_cleanup_stale,
        wipe_fisnotes=not args.no_wipe_fisnotes,
    )
    print(
        "Desktop FIS scan complete: "
        f"folders={folders}; files={files}; db={db_path}; root_html={root / 'FIS.html'}; "
        f"file_notes={notes} written/{note_skips} preserved/{stale} stale removed/{wiped} pre-wiped; "
        f"local_ai={enriched} enriched/{failed} skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
