"""Opt-in QA metadata only. Never records input text or runs business tools."""
import json
import logging
import os
from pathlib import Path

BUILD = '20261029.24'
logger = logging.getLogger(__name__)


def write_diagnostic(name, values):
    root = os.environ.get('RAT_MINI_ACCEPTANCE_DIR')
    if not root:
        return True
    try:
        folder = Path(root)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        temporary = folder / (name + '.tmp')
        temporary.write_text(json.dumps(dict(build=BUILD, pid=os.getpid(), **values), ensure_ascii=False, indent=2))
        temporary.replace(target)
        return True
    except Exception as exc:
        # Avoid an exception repr that could contain user data from a serializer.
        logger.warning('qa_metadata_write_failed name=%s type=%s', name, type(exc).__name__)
        return False
