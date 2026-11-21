from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_main():
    module_path = Path(__file__).resolve().parent / "organize" / "proof_router.py"
    spec = importlib.util.spec_from_file_location("proof_router_standalone", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
