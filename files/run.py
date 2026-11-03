#!/usr/bin/env python3
"""run.py — CLI entry point for 02_INVENTORY.

Usage:
    python 02_INVENTORY/run.py "D:\path\to\folder"
    python 02_INVENTORY/run.py                      # opens folder picker
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Resolve paths relative to David-OSv3 root
SCRIPT_DIR = Path(__file__).resolve().parent
DAVIDOSV3 = SCRIPT_DIR.parent
OUTBOX = SCRIPT_DIR / "OUTBOX"
PROFILES_PATH = DAVIDOSV3 / "config" / "folder_profiles.json"


def load_profile(folder: Path) -> dict | None:
    """Load the profile for a folder from folder_profiles.json."""
    if not PROFILES_PATH.exists():
        return None
    try:
        profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    folder_str = str(folder).replace("/", "\\").rstrip("\\").lower()

    # Try exact match first, then prefix match
    for key, prof in profiles.items():
        key_norm = key.replace("/", "\\").rstrip("\\").lower()
        if key_norm == folder_str:
            return prof

    # Try matching by folder name
    for key, prof in profiles.items():
        if Path(key).name.lower() == folder.name.lower():
            return prof

    return None


def pick_folder() -> Path | None:
    """Simple folder picker — try tkinter, fall back to input()."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title="Select folder to inventory")
        root.destroy()
        if path:
            return Path(path)
        return None
    except ImportError:
        raw = input("Folder path: ").strip().strip('"')
        if raw:
            return Path(raw)
        return None


def main():
    from inventory_core import inventory_folder, write_inventory

    # Get folder
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
    else:
        folder = pick_folder()
        if not folder:
            print("No folder selected.")
            sys.exit(1)

    folder = folder.resolve()
    if not folder.is_dir():
        print(f"ERROR: Not a directory: {folder}")
        sys.exit(1)

    # Load profile if available
    profile = load_profile(folder)
    if profile:
        print(f"Profile found: folder_class={profile.get('folder_class', '?')}")
    else:
        print("No profile found — using container code UNK. Run 01_PROFILE first for proper UIDs.")

    # Run inventory
    print(f"\nInventorying: {folder}")
    print("Hashing files...")

    result = inventory_folder(folder, profile=profile, max_depth=2)

    # Write output
    paths = write_inventory(result, OUTBOX)

    # Summary
    print(f"\n{'='*60}")
    print(f"INVENTORY COMPLETE: {folder.name}")
    print(f"{'='*60}")
    print(f"  Container:     TP-{result.container_code}")
    print(f"  Total files:   {result.total_files}")
    print(f"  Content files: {result.content_files}")
    print(f"  Duplicates:    {result.duplicates}")
    print(f"  Problems:      {result.problems}")
    print(f"\nOutput:")
    for label, p in paths.items():
        print(f"  {label}: {p}")
    print()


if __name__ == "__main__":
    main()
