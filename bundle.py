"""Backward-compatibility shim for reasoning.bundle.

Canonical implementation lives in reasoning.bundle.
This module aliases the canonical module in sys.modules so symbol identity,
private helpers, and monkeypatching behave identically.
"""

import sys
from reasoning import bundle as _canonical

_shim_name = __name__
globals().update({k: getattr(_canonical, k) for k in dir(_canonical)})
sys.modules[_shim_name] = _canonical
