"""Backward-compatibility shim for reasoning.reasoning_env.

Canonical implementation lives in reasoning.reasoning_env.
This module aliases the canonical module in sys.modules so symbol identity,
private helpers, and monkeypatching behave identically.
"""

import sys
from reasoning import reasoning_env as _canonical

_shim_name = __name__
globals().update({k: getattr(_canonical, k) for k in dir(_canonical)})
sys.modules[_shim_name] = _canonical
