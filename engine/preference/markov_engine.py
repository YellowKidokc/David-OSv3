"""Legacy state-path adapter for the canonical naming model."""
from prediction.naming.markov_engine import MarkovEngine as _Canonical
import config
class MarkovEngine(_Canonical):
    def __init__(self):
        super().__init__(state_file=config.DB_DIR / "pref_markov.json")
