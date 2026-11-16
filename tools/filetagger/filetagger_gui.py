"""Compatibility entry point; canonical tagger code lives in Theophysics_Tagger."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.tagger_v3 import gui as main
if __name__ == "__main__": main()
