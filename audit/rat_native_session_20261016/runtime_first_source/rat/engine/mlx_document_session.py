"""Explicitly loaded native MLX session for one document context at a time.

No UI, service, automatic download or provider fallback. Keep one prepared
document prefix; each question generates a fresh answer from its own cache copy.
The research backends and default RAT model selection do not use this module.
"""
from __future__ import annotations

import copy
from pathlib import Path
import threading
import time


def _native_backend():
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.models.cache import make_prompt_cache
    from mlx_lm.sample_utils import make_sampler

    class Native:
        @staticmethod
        def load(path):
            return load(str(path), tokenizer_config={
                'local_files_only': True, 'trust_remote_code': False}, lazy=False)

        @staticmethod
        def prepare(model, tokens, check=None):
            cache = make_prompt_cache(model)
            for offset in range(0, len(tokens), 256):
                if check:
                    check()
                model(mx.array(tokens[offset:offset + 256])[None], cache=cache)
                mx.eval([layer.state for layer in cache])
            if check:
                check()
            return cache

        @staticmethod
        def generate(model, tokenizer, tokens, cache, max_tokens, check):
            return stream_generate(model, tokenizer, prompt=tokens, prompt_cache=cache,
                sampler=make_sampler(temp=0), max_tokens=max_tokens, prefill_step_size=256,
                prompt_progress_callback=lambda *_: check())

        @staticmethod
        def clear():
            mx.synchronize()
            mx.clear_cache()

    return Native


class MLXDocumentSession:
    """Inject as selected-document Q&A's model_client after explicit load().

    load()/prepare_context() are blocking preparation operations: use an app-owned
    inference worker, never the GUI thread. close() releases session references.
    """

    def __init__(self, model_path, *, max_context_tokens=4096, _backend_factory=None):
        path = Path(model_path).expanduser()
        if (not path.is_absolute() or not path.is_dir()
                or not (path / 'config.json').is_file()
                or not (path / 'tokenizer.json').is_file()
                or not any(path.glob('*.safetensors'))):
            raise ValueError('native_model_requires_complete_local_directory')
        if type(max_context_tokens) is not int or max_context_tokens < 128:
            raise ValueError('invalid_native_context_budget')
        self.model_path = path.resolve()
        cache_name = self.model_path.parent.parent.name
        label = cache_name.removeprefix('models--').replace('--', '/') if cache_name.startswith('models--') else path.name
        self.model = 'mlx:' + label
        self.max_context_tokens = max_context_tokens
        self._factory = _backend_factory or _native_backend
        self._backend = self._weights = self._tokenizer = None
        self._prefix_tokens = ()
        self._prefix_cache = None
        self._lock = threading.RLock()

    @property
    def is_loaded(self):
        return self._weights is not None

    def load(self):
        started = time.perf_counter()
        with self._lock:
            if not self.is_loaded:
                backend = self._factory()
                weights, tokenizer = backend.load(self.model_path)
                self._backend, self._weights, self._tokenizer = backend, weights, tokenizer
        return time.perf_counter() - started

    def _tokens(self, messages, *, generation):
        if (not isinstance(messages, list) or not messages
                or any(not isinstance(m, dict) or m.get('role') not in ('system', 'user')
                       or not isinstance(m.get('content'), str) for m in messages)):
            raise ValueError('native_document_messages_required')
        return tuple(self._tokenizer.apply_chat_template(messages, tokenize=True,
            add_generation_prompt=generation, enable_thinking=False))

    def _prepare(self, tokens, check=None):
        if tokens != self._prefix_tokens or self._prefix_cache is None:
            # Drop the previous document before allocating another context.
            self._prefix_tokens, self._prefix_cache = (), None
            self._prefix_cache = self._backend.prepare(self._weights, tokens, check)
            self._prefix_tokens = tokens

    def prepare_context(self, messages):
        """Read a selected document's system/context messages once, before a question."""
        with self._lock:
            if not self.is_loaded:
                raise RuntimeError('native_model_not_loaded')
            tokens = self._tokens(messages, generation=False)
            if not tokens or len(tokens) >= self.max_context_tokens:
                raise ValueError('native_document_context_too_large')
            started = time.perf_counter()
            self._prepare(tokens)
            return dict(prefill_s=time.perf_counter() - started, prefix_tokens=len(tokens))

    def chat_with_meta(self, messages, tools, timeout=90, max_tokens=640, thinking=False,
                       response_format=None, *, on_text=None, should_cancel=None):
        started = time.perf_counter()
        meta = dict(message={}, prompt_tokens=0, completion_tokens=0, token_usage_known=False,
                    done_reason=None, error=None, request={'model': self.model,
                    'messages': messages, 'tools': tools}, raw_response=None)

        def check():
            if should_cancel and should_cancel():
                raise RuntimeError('cancelled')
            if time.perf_counter() - started >= timeout:
                raise TimeoutError('native_document_timeout')

        try:
            if tools or response_format or thinking:
                raise ValueError('native_document_session_does_not_support_agent_protocol')
            if type(max_tokens) is not int or max_tokens < 1 or timeout <= 0:
                raise ValueError('invalid_native_generation_budget')
            # Include time waiting for another inference operation in the budget.
            if not self._lock.acquire(timeout=timeout):
                raise TimeoutError('native_document_timeout')
            try:
                check()
                if not self.is_loaded:
                    raise RuntimeError('native_model_not_loaded')
                if (not isinstance(messages, list) or len(messages) < 2
                        or not isinstance(messages[-1], dict) or messages[-1].get('role') != 'user'):
                    raise ValueError('native_document_question_required')
                full = self._tokens(messages, generation=True)
                prefix = self._tokens(messages[:-1], generation=False)
                if len(full) + max_tokens > self.max_context_tokens:
                    raise ValueError('native_document_context_too_large')
                if not prefix or full[:len(prefix)] != prefix or len(full) <= len(prefix):
                    raise ValueError('native_document_template_prefix_mismatch')
                meta['prompt_tokens'] = len(full)
                already_prepared = prefix == self._prefix_tokens and self._prefix_cache is not None
                self._prepare(prefix, check)
                check()
                cached = copy.deepcopy(self._prefix_cache)
                generator = self._backend.generate(self._weights, self._tokenizer,
                    full[len(prefix):], cached, max_tokens, check)
                text = ''
                final = None
                first_text = None
                try:
                    for part in generator:
                        check()
                        text += part.text
                        if part.text.strip() and first_text is None:
                            first_text = time.perf_counter() - started
                        if on_text and part.text:
                            on_text(part.text)
                        final = part
                finally:
                    generator.close()
                check()
                if final is None or not text.strip():
                    raise RuntimeError('empty_native_document_answer')
                meta.update(message={'role': 'assistant', 'content': text.strip()},
                    completion_tokens=final.generation_tokens, token_usage_known=True,
                    done_reason=final.finish_reason, raw_response=dict(
                        reused_prefix_tokens=len(prefix), prefix_already_prepared=already_prepared,
                        newly_submitted_tokens=len(full)-len(prefix), first_text_s=first_text))
                if final.finish_reason != 'stop':
                    meta['error'] = 'native_document_output_truncated'
            finally:
                self._lock.release()
        except Exception as error:
            meta.update(error=str(error) or type(error).__name__, message={})
        meta['duration_ms'] = (time.perf_counter() - started) * 1000
        return meta

    def close(self):
        with self._lock:
            backend = self._backend
            self._prefix_cache, self._prefix_tokens = None, ()
            self._weights = self._tokenizer = self._backend = None
            if backend is not None:
                backend.clear()
