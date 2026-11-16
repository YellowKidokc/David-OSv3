"""Compatibility launcher for canonical Tagger v3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.tagger_v3 import gui as main
if __name__ == "__main__":
    main()
