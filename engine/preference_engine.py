"""
preference_engine.py — backward-compat shim.

The preference engine is now a pluggable ensemble of several engines (River,
sklearn-GBDT, Vowpal Wabbit, a frequency baseline, and a best-effort MS
Recommenders / LightGBM adapter). See the `preference/` package. This module
keeps the old `get_engine()` entry point working for existing imports.
"""
from __future__ import annotations

from preference.ensemble import get_ensemble, backtest   # noqa: F401


def get_engine():
    return get_ensemble()
