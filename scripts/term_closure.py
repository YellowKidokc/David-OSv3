from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.term_closure import plan_closure

def main() -> int:
    p = argparse.ArgumentParser(description="Observe/propose-only topic closure planner")
    p.add_argument("--topic", required=True); p.add_argument("--root", action="append", required=True, type=Path)
    p.add_argument("--term", action="append", default=[]); p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(); print(json.dumps(plan_closure(a.root, a.output, a.topic, a.term), indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
