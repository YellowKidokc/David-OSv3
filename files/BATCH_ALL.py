#!/usr/bin/env python3
"""BATCH_ALL.py — run the full pipeline across every source folder.

Usage:
    python BATCH_ALL.py                           # uses default folder list
    python BATCH_ALL.py --folders folders.json     # custom folder list
    python BATCH_ALL.py --folder "D:\some\path"   # single folder

Pipeline per folder:
    01_PROFILE  →  04_ADAPT (if legacy cards)  →  02_INVENTORY  →  03_CLASSIFY (queue)

This script does NOT run 03_CLASSIFY automatically — classification needs
human rulings. It queues folders for the review GUI instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DAVIDOSV3 = Path(__file__).resolve().parent
BATCH_LOG = DAVIDOSV3 / "data" / "batch_runs"

# Default source folders — everything that holds papers
DEFAULT_FOLDERS = [
    # Vault
    r"O:\_Theophysics_v5",
    # Production
    r"C:\Users\David\Documents\faiththruphysics.com",
    # Canon builds
    r"C:\theophysics",
    # Evidence chain
    r"D:\GitHub\David-OSv3\_FIS_ROOT_SIDECAR_ARCHIVE\EVIDENCE",
    # Desktop working folders (add as needed)
    # r"H:\Desktop 2\MASTER_EQUATION_TEST",
]


@dataclass
class FolderRun:
    folder: str
    status: str = "pending"      # pending | profiled | adapted | inventoried | queued | error
    profile_found: bool = False
    legacy_cards: int = 0
    files_found: int = 0
    content_files: int = 0
    duplicates: int = 0
    problems: int = 0
    error: str = ""
    started: str = ""
    finished: str = ""


@dataclass
class BatchRun:
    run_id: str
    started: str
    folders: list[FolderRun] = field(default_factory=list)
    finished: str = ""


def check_legacy_cards(folder: Path) -> int:
    """Count legacy sidecar cards (type: definition, no mim.v1 stamp)."""
    count = 0
    sidecars_dir = folder / "sidecars"
    if not sidecars_dir.is_dir():
        return 0
    for f in sidecars_dir.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")[:500]
            if "type:" in text and "definition" in text and "mim.v1" not in text:
                count += 1
        except OSError:
            pass
    return count


def run_step(step_name: str, script: Path, folder: Path) -> tuple[bool, str]:
    """Run a pipeline step as a subprocess. Returns (success, output)."""
    if not script.exists():
        return False, f"Script not found: {script}"
    try:
        result = subprocess.run(
            [sys.executable, str(script), str(folder)],
            capture_output=True, text=True, timeout=300,
            cwd=str(script.parent),
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"{step_name} timed out (300s)"
    except Exception as e:
        return False, f"{step_name} error: {e}"


def process_folder(folder_path: str, run_record: FolderRun) -> None:
    """Run the full pipeline on one folder."""
    folder = Path(folder_path)
    run_record.started = datetime.now(timezone.utc).isoformat()

    if not folder.is_dir():
        run_record.status = "error"
        run_record.error = f"Not a directory: {folder}"
        run_record.finished = datetime.now(timezone.utc).isoformat()
        return

    print(f"\n{'='*60}")
    print(f"  {folder}")
    print(f"{'='*60}")

    # --- Step 1: Check if profiled ---
    profiles_path = DAVIDOSV3 / "config" / "folder_profiles.json"
    profile = None
    if profiles_path.exists():
        try:
            profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
            folder_str = str(folder).replace("/", "\\").rstrip("\\").lower()
            for key, prof in profiles.items():
                if key.replace("/", "\\").rstrip("\\").lower() == folder_str:
                    profile = prof
                    break
            if not profile:
                for key, prof in profiles.items():
                    if Path(key).name.lower() == folder.name.lower():
                        profile = prof
                        break
        except (json.JSONDecodeError, OSError):
            pass

    if profile:
        run_record.profile_found = True
        run_record.status = "profiled"
        print(f"  [01] Profile: found (folder_class={profile.get('folder_class', '?')})")
    else:
        # Run 01_PROFILE
        profile_script = DAVIDOSV3 / "01_PROFILE" / "run.py"
        if profile_script.exists():
            print(f"  [01] Profile: running...")
            ok, out = run_step("01_PROFILE", profile_script, folder)
            if ok:
                run_record.profile_found = True
                run_record.status = "profiled"
                print(f"  [01] Profile: done")
            else:
                print(f"  [01] Profile: FAILED — continuing without profile")
                print(f"       {out[:200]}")
        else:
            print(f"  [01] Profile: script not found — continuing without profile")

    # --- Step 2: Check for legacy cards, run 04_ADAPT if needed ---
    legacy_count = check_legacy_cards(folder)
    run_record.legacy_cards = legacy_count
    if legacy_count > 0:
        adapt_script = DAVIDOSV3 / "04_ADAPT" / "run.py"
        if adapt_script.exists():
            print(f"  [04] Adapt: {legacy_count} legacy cards found, running...")
            ok, out = run_step("04_ADAPT", adapt_script, folder)
            if ok:
                run_record.status = "adapted"
                print(f"  [04] Adapt: done")
            else:
                print(f"  [04] Adapt: FAILED — continuing")
                print(f"       {out[:200]}")
        else:
            print(f"  [04] Adapt: {legacy_count} legacy cards but no script")
    else:
        print(f"  [04] Adapt: no legacy cards, skipping")

    # --- Step 3: Run 02_INVENTORY ---
    inv_script = DAVIDOSV3 / "02_INVENTORY" / "run.py"
    if inv_script.exists():
        print(f"  [02] Inventory: running...")
        ok, out = run_step("02_INVENTORY", inv_script, folder)
        if ok:
            run_record.status = "inventoried"
            # Try to parse counts from output
            for line in out.split("\n"):
                if "Total files:" in line:
                    try:
                        run_record.files_found = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Content files:" in line:
                    try:
                        run_record.content_files = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Duplicates:" in line:
                    try:
                        run_record.duplicates = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Problems:" in line:
                    try:
                        run_record.problems = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
            print(f"  [02] Inventory: {run_record.content_files} content files, "
                  f"{run_record.duplicates} dupes, {run_record.problems} problems")
        else:
            run_record.status = "error"
            run_record.error = f"Inventory failed: {out[:200]}"
            print(f"  [02] Inventory: FAILED")
            print(f"       {out[:200]}")
    else:
        print(f"  [02] Inventory: script not found")
        run_record.status = "error"
        run_record.error = "02_INVENTORY/run.py not found"

    # --- Step 4: Queue for 03_CLASSIFY ---
    if run_record.status == "inventoried":
        run_record.status = "queued"
        print(f"  [03] Classify: QUEUED for review (run REVIEW.bat)")

    run_record.finished = datetime.now(timezone.utc).isoformat()


def main():
    # Parse args
    folders = list(DEFAULT_FOLDERS)

    if "--folders" in sys.argv:
        idx = sys.argv.index("--folders") + 1
        if idx < len(sys.argv):
            fp = Path(sys.argv[idx])
            folders = json.loads(fp.read_text(encoding="utf-8"))
    elif "--folder" in sys.argv:
        idx = sys.argv.index("--folder") + 1
        if idx < len(sys.argv):
            folders = [sys.argv[idx]]

    # Filter to folders that actually exist
    existing = [f for f in folders if Path(f).is_dir()]
    missing = [f for f in folders if not Path(f).is_dir()]

    print(f"\n{'#'*60}")
    print(f"  BATCH_ALL — David-OS Pipeline")
    print(f"  {len(existing)} folders to process")
    if missing:
        print(f"  {len(missing)} folders not found (skipped)")
        for m in missing:
            print(f"    MISSING: {m}")
    print(f"{'#'*60}")

    # Set up run log
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch = BatchRun(
        run_id=run_id,
        started=datetime.now(timezone.utc).isoformat(),
    )

    # Process each folder
    for folder_path in existing:
        run_record = FolderRun(folder=folder_path)
        batch.folders.append(run_record)
        process_folder(folder_path, run_record)

    batch.finished = datetime.now(timezone.utc).isoformat()

    # Write batch log
    BATCH_LOG.mkdir(parents=True, exist_ok=True)
    log_path = BATCH_LOG / f"batch_{run_id}.json"
    log_path.write_text(
        json.dumps(asdict(batch), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Summary
    print(f"\n{'#'*60}")
    print(f"  BATCH COMPLETE")
    print(f"{'#'*60}")
    print(f"\n  {'Folder':<50} {'Status':<15} {'Files':<8} {'Dupes':<8}")
    print(f"  {'-'*50} {'-'*15} {'-'*8} {'-'*8}")
    for fr in batch.folders:
        name = Path(fr.folder).name[:48]
        print(f"  {name:<50} {fr.status:<15} {fr.content_files:<8} {fr.duplicates:<8}")

    queued = sum(1 for fr in batch.folders if fr.status == "queued")
    errors = sum(1 for fr in batch.folders if fr.status == "error")
    print(f"\n  Queued for classification: {queued}")
    if errors:
        print(f"  Errors: {errors}")
    print(f"\n  Log: {log_path}")
    print(f"\n  Next: run 03_CLASSIFY\\REVIEW.bat to classify queued folders\n")


if __name__ == "__main__":
    main()
