"""Legacy state-path adapter for the canonical naming model."""
from prediction.naming.frequency import FrequencyEngine as _Canonical
import config
from .features import feature_key
class FrequencyEngine(_Canonical):
    def __init__(self):
        super().__init__(state_file=config.DB_DIR / "pref_frequency.json", feature_key=feature_key)
