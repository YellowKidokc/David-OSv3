"""
preference/ — pluggable preference-engine framework.

Multiple engines each predict P(approve) for a naming proposal. We don't know
which is best, so we run several, can blend or cascade them, and can backtest
them against the decision log (`compare`). Every engine implements the same
small interface (see base.PreferenceEngine), so adding one is a single file.

Engines that run today: frequency (baseline), river (online logistic),
sklearn_gbdt (batch), vowpal_wabbit (online). The MS-Recommenders adapter is
best-effort (lights up when its deps are installed).
"""
from .ensemble import get_ensemble, Ensemble          # noqa: F401
from .base import PreferenceEngine                     # noqa: F401
