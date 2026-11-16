"""Legacy resident entry point; all watching is owned by Tagger v3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.tagger_v3 import watch_legacy_config
if __name__ == '__main__':
    watch_legacy_config(Path(__file__).with_name('daemon_config.json'))
