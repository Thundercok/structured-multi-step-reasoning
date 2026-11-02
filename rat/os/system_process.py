"""Environment for macOS system executables, without mutating the app runtime."""
import os
from pathlib import Path
import sys


def system_environment():
    environment = dict(os.environ)
    bundle = getattr(sys, '_MEIPASS', None)
    if bundle:
        base = Path(bundle).resolve()
        for key in ('DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH',
                    'DYLD_FALLBACK_LIBRARY_PATH', 'DYLD_FALLBACK_FRAMEWORK_PATH'):
            value = environment.get(key + '_ORIG', environment.get(key, ''))
            # Runtime hooks may prepend bundled libraries. Retain user/system
            # entries; never change TCC, HOME, identity or the parent process.
            entries = [entry for entry in value.split(os.pathsep)
                       if entry and not Path(entry).resolve().is_relative_to(base)]
            if entries:
                environment[key] = os.pathsep.join(entries)
            else:
                environment.pop(key, None)
    return environment
