"""Compatibility entry point; implementation is owned by fis.fis_namer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == "__main__":
    import runpy
    runpy.run_module("fis.fis_namer", run_name="__main__")
else:
    from importlib import import_module
    _implementation = import_module("fis.fis_namer")
    globals().update({k: v for k, v in vars(_implementation).items()
                      if not k.startswith("__")})
