"""Legacy-path stub for file-intelligence-system/fis_classifier.py. Holds NO implementation."""
import runpy, sys
from pathlib import Path
CANONICAL = Path(r"D:\GitHub\David-OSv3\apps\classify\src\engines\fis\fis_classifier.py")
print(f"[moved] fis_classifier now lives at {CANONICAL}  (forwarding...)", file=sys.stderr)
sys.path.insert(0, str(CANONICAL.parent))
if __name__ == "__main__":
    runpy.run_path(str(CANONICAL), run_name="__main__")
else:
    from fis_classifier import *  # noqa: F401,F403
