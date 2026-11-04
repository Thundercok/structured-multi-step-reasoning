"""HTTPS JSON requests for the online translation providers."""
from __future__ import annotations

import ssl

import certifi

from rat.engine.http_transport import post_json


def request_json(url, payload=None, *, headers=None, timeout=15, should_cancel=lambda: False, method='POST'):
    return post_json(url, payload, timeout=timeout, should_cancel=should_cancel,
                     headers=headers, method=method,
                     ssl_context=ssl.create_default_context(cafile=certifi.where()))
