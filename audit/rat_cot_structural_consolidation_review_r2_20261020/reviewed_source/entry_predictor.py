"""Backward-compatibility shim for reasoning.entry_predictor.

Canonical implementation lives in reasoning.entry_predictor.
This module aliases the canonical module in sys.modules so symbol identity,
private helpers, and monkeypatching behave identically.
"""

import sys
from reasoning import entry_predictor as _canonical

_shim_name = __name__
globals().update({k: getattr(_canonical, k) for k in dir(_canonical)})
sys.modules[_shim_name] = _canonical
