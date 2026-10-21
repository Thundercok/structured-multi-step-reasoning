"""Resident native document model, with one inference thread and explicit ownership.

Constructing this object neither imports MLX nor loads weights. Startup callers
may load() on a worker, or let the first question load it. No network provider,
model download, global service, GUI dependency, or automatic backend fallback.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import threading
import time

from rat.engine.mlx_document_session import MLXDocumentSession


class ResidentDocumentModel:
    supports_document_callbacks = True

    def __init__(self, model_path, *, max_context_tokens=4096, _session_factory=None):
        factory = _session_factory or MLXDocumentSession
        self._client = factory(model_path, max_context_tokens=max_context_tokens)
        self.model = self._client.model
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='rat-document')
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._closed = False
        self._worker = threading.local()

    @property
    def is_loaded(self):
        return self._client.is_loaded

    def _submit(self, callback):
        if getattr(self._worker, 'active', False):
            raise RuntimeError('document_model_reentrant_call')

        def run():
            self._worker.active = True
            try:
                return callback()
            finally:
                self._worker.active = False

        with self._lock:
            if self._closed:
                raise RuntimeError('document_model_closed')
            return self._executor.submit(run)

    def load(self):
        """Blocking startup preparation; all native operations stay on one thread."""
        return self._submit(self._client.load).result()

    def unload(self):
        """Release model/context; a later question may load them again."""
        self._submit(self._client.close).result()

    def chat_with_meta(self, messages, tools, timeout=90, max_tokens=640, thinking=False,
                       response_format=None, *, on_text=None, should_cancel=None):
        started = time.perf_counter()
        aborted = threading.Event()

        def check():
            if aborted.is_set() or self._stop.is_set() or (should_cancel and should_cancel()):
                raise RuntimeError('cancelled')
            if time.perf_counter() - started >= timeout:
                raise TimeoutError('native_document_timeout')

        def infer():
            check()
            was_loaded = self.is_loaded
            load_s = self._client.load()
            check()
            result = self._client.chat_with_meta(messages, tools,
                timeout=timeout - (time.perf_counter() - started), max_tokens=max_tokens,
                thinking=thinking, response_format=response_format, on_text=on_text,
                should_cancel=lambda: aborted.is_set() or self._stop.is_set()
                    or bool(should_cancel and should_cancel()))
            result['preparation'] = dict(loaded_for_request=not was_loaded, load_s=load_s)
            return result

        try:
            if tools or response_format or thinking:
                raise ValueError('native_document_session_does_not_support_agent_protocol')
            if type(max_tokens) is not int or max_tokens < 1 or timeout <= 0:
                raise ValueError('invalid_native_generation_budget')
            future = self._submit(infer)
            try:
                while True:
                    check()
                    try:
                        result = future.result(timeout=0.05)
                        break
                    except FutureTimeout:
                        if future.done():
                            raise
            except BaseException:
                aborted.set()
                future.cancel()
                raise
        except Exception as error:
            result = dict(message={}, error=str(error) or type(error).__name__,
                prompt_tokens=0, completion_tokens=0, token_usage_known=False,
                done_reason=None, raw_response=None,
                request=dict(model=self.model, messages=messages, tools=tools))
        result['duration_ms'] = (time.perf_counter() - started) * 1000
        return result

    def close(self):
        """Cancel pending inference and release native resources on their owner thread."""
        if getattr(self._worker, 'active', False):
            raise RuntimeError('document_model_reentrant_close')
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            release = self._executor.submit(self._client.close)
        try:
            release.result()
        finally:
            self._executor.shutdown(wait=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
