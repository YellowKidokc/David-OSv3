"""Legacy-path stub for 03_CLASSIFY/03_RENAMING/rename_engine.py. Holds NO implementation.
NOTE: the Renamer window (renamer_gui.py) also uses apply()/undo from this module,
so this stub must not replace the original until the window is migrated too."""
import runpy, sys
from pathlib import Path
CANONICAL = Path(r"D:\GitHub\David-OSv3\apps\rename\src\engine\rename_engine.py")
print(f"[moved] rename_engine now lives at {CANONICAL}  (forwarding...)", file=sys.stderr)
sys.path.insert(0, str(CANONICAL.parent))
if __name__ == "__main__":
    runpy.run_path(str(CANONICAL), run_name="__main__")
else:
    from rename_engine import *  # noqa: F401,F403
