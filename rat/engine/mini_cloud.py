"""Cloud adapter for the existing AssistantRuntime; no alternate agent loop."""
from __future__ import annotations

import json
import copy
import ssl
import time

import certifi

from rat.engine.http_transport import post_json
from rat.engine.mini_settings import keychain_key


ENDPOINTS = {'openai': 'https://api.openai.com/v1/chat/completions',
             'deepseek': 'https://api.deepseek.com/chat/completions',
             'groq': 'https://api.groq.com/openai/v1/chat/completions'}


def request_json(url, payload=None, *, headers=None, timeout=15, should_cancel=lambda: False, method='POST'):
    return post_json(url, payload, timeout=timeout, should_cancel=should_cancel,
                     headers=headers, method=method,
                     ssl_context=ssl.create_default_context(cafile=certifi.where()))


class CloudModelClient:
    supports_chat_callbacks = True

    def __init__(self, settings, key_reader=keychain_key):
        self.settings, self.key_reader = settings, key_reader
        self.begin_turn()

    def begin_turn(self):
        self.calls, self.responses, self.generated, self.usage_unknown = 0, 0, 0, False
        self.deadline = time.monotonic() + 45

    def chat_with_meta(self, messages, tools, *, should_cancel=lambda: False, response_format=None):
        # Explicit Mini opt-in applies to planning and LLM translation alike.
        # Check before credentials, serialization or any network request.
        if self.settings.get('llm_enabled') is not True:
            raise ValueError('mini_llm_disabled')
        provider = self.settings['provider']
        if provider not in ENDPOINTS:
            raise ValueError('unknown_cloud_provider')
        if self.calls >= 4 or self.generated >= 2048 or time.monotonic() >= self.deadline:
            raise ValueError('budget_exhausted')
        key = self.key_reader(provider)
        if not key:
            raise ValueError('api_key_missing: Hãy cấu hình API trong Cài đặt; tìm file và dịch trực tiếp vẫn dùng được.')
        if len(json.dumps(messages, ensure_ascii=False).encode()) > 32_000:
            raise ValueError('model_context_too_large')
        messages = copy.deepcopy(messages)
        for message in messages:
            for call in message.get('tool_calls') or []:
                if isinstance(call.get('function', {}).get('arguments'), dict):
                    call['function']['arguments'] = json.dumps(call['function']['arguments'], ensure_ascii=False)
        payload = {'model': self.settings['model'], 'messages': messages,
                   'max_tokens': min(768, 2048 - self.generated), 'temperature': 0.1}
        if response_format:
            # Keep the provider wire format small and portable. The shared
            # runtime validates the returned JSON against this exact schema.
            payload['response_format'] = {'type': 'json_object'}
            payload['messages'].append({'role': 'system', 'content':
                'Return only a JSON object matching this schema: ' +
                json.dumps(response_format, ensure_ascii=False, separators=(',', ':'))})
        if tools:
            payload['tools'] = tools
        if provider == 'deepseek':
            payload['thinking'] = {'type': 'disabled'}
        if len(json.dumps(payload['messages'], ensure_ascii=False).encode()) > 32_000:
            raise ValueError('model_context_too_large')
        self.calls += 1
        raw = request_json(ENDPOINTS[provider], payload, headers={'Authorization': 'Bearer ' + key},
                           timeout=max(0.1, min(25, self.deadline - time.monotonic())),
                           should_cancel=should_cancel)
        self.responses += 1
        message = raw['choices'][0]['message']
        if raw['choices'][0].get('finish_reason') == 'length':
            raise ValueError('model_output_truncated')
        # Normalize native tool arguments to RAT's existing adapter protocol.
        for call in message.get('tool_calls') or []:
            args = call['function'].get('arguments', '{}')
            if isinstance(args, str):
                call['function']['arguments'] = json.loads(args)
        usage = raw.get('usage') or {}
        self.usage_unknown |= not bool(usage)
        self.generated += int(usage.get('completion_tokens', 0))
        return {'message': {k: v for k, v in message.items() if k in ('role', 'content', 'tool_calls')},
                'prompt_tokens': int(usage.get('prompt_tokens', 0)),
                'completion_tokens': int(usage.get('completion_tokens', 0)),
                'usage_unknown': not bool(usage)}
