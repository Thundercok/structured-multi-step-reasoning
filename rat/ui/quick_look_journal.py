"""Bounded transport/execution metadata. Never accepts source text or pixels."""
from collections import deque
import json
import logging
import os
import time
from threading import RLock
from uuid import uuid4


class QuickLookJournal:
    def __init__(self, root, build):
        self.path = root / 'last-hotkey.json'
        self.build = build
        self.events = deque(maxlen=32)
        self.sequence = 0
        self.helper_state = 'unknown'
        self.helper_pid = None
        self.lock = RLock()

    @staticmethod
    def invocation_id():
        return 'ql-' + uuid4().hex

    def record(self, stage, *, invocation_id=None, **metadata):
        with self.lock:
            self._record(stage, invocation_id=invocation_id, **metadata)

    def _record(self, stage, *, invocation_id=None, **metadata):
        self.sequence += 1
        event = dict(sequence=self.sequence, monotonic_s=time.monotonic(),
            stage=stage, pid=os.getpid(), ui_build=self.build)
        if invocation_id:
            event['invocation_id'] = invocation_id
        for name in ('helper_pid', 'state', 'reason', 'exit_code', 'exit_status',
                     'generation', 'execution_id', 'artifact_id'):
            if metadata.get(name) is not None:
                event[name] = metadata[name]
        self.events.append(event)
        if metadata.get('state'):
            self.helper_state = metadata['state']
        if metadata.get('helper_pid'):
            self.helper_pid = metadata['helper_pid']
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(event, protocol='SELECT1', helper_state=self.helper_state,
                last_helper_pid=self.helper_pid, events=list(self.events))))
            temporary.replace(self.path)
        except Exception as exc:
            # Recording cannot break the shortcut or a valid tool result.
            logging.getLogger(__name__).warning('quicklook_metadata_failed type=%s', type(exc).__name__)
