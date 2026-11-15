"""Compatibility entry point for the canonical FIS classifier."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == "__main__":
    import runpy
    runpy.run_module("fis.fis_classifier", run_name="__main__")
else:
    from fis.fis_classifier import *  # noqa: F401,F403
