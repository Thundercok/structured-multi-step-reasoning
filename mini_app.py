"""RAT Mini: python mini_app.py (use the repository's Python environment)."""
import sys
import os
import json
from pathlib import Path

if __name__ == '__main__':
    recording = os.environ.get('RAT_MINI_ACCEPTANCE_DIR')
    if recording:
        directory = Path(recording)
        directory.mkdir(parents=True, exist_ok=True)
        (directory/'launch.json').write_text(json.dumps({'pid':os.getpid(),'entrypoint':'mini_app.py','status':'starting'}))
    if '--check-bundle' in sys.argv:
        from rat.mini_bundle_check import main
    else:
        from rat.ui.mini_quick import main
    sys.exit(main())
