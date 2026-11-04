"""Keep every test away from the real ~/.rat state, whose index holds a person's files."""
import atexit
import os
import shutil
import tempfile

_state = tempfile.mkdtemp(prefix="rat_tests_")
atexit.register(shutil.rmtree, _state, ignore_errors=True)
os.environ.setdefault("RAT_STATE_DIR", _state)
