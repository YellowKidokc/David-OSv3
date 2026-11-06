"""Legacy-path stub for fingerprint.py. Holds NO implementation.

To be dropped in place of an old fingerprint.py once the user approves.
Prints where the canonical app lives and forwards the same CLI arguments to it.
"""
import runpy, sys
from pathlib import Path

CANONICAL = Path(r"D:\GitHub\David-OSv3\apps\fingerprint\src\fingerprint.py")
print(f"[moved] fingerprint now lives at {CANONICAL.parent.parent}  (forwarding...)", file=sys.stderr)
if __name__ == "__main__":
    sys.path.insert(0, str(CANONICAL.parent))
    runpy.run_path(str(CANONICAL), run_name="__main__")
else:
    sys.path.insert(0, str(CANONICAL.parent))
    from fingerprint import *  # noqa: F401,F403  re-export for importers
