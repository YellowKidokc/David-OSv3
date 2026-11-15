"""Compatibility entry point; canonical tagger code lives in Theophysics_Tagger."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import runpy
CANONICAL = ROOT / "Theophysics_Tagger" / "tools" / "ext_filetagger" / "read_math_templates.py"
sys.path.insert(0, str(CANONICAL.parent))
if __name__ == "__main__":
    runpy.run_path(str(CANONICAL), run_name="__main__")
else:
    globals().update({k: v for k, v in runpy.run_path(str(CANONICAL)).items() if not k.startswith('__')})
