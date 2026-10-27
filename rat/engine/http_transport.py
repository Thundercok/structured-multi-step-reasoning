"""Request-scoped JSON transport with cancellation during inference waits."""
from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from urllib.parse import urlsplit


class RequestCancelled(Exception):
    pass


def post_json(url, payload, *, timeout, should_cancel, headers=None, ssl_context=None,
              method="POST", max_body_bytes=2_000_000):
    """Abort this socket on cancellation/deadline, including before headers.

    Closing an HTTPConnection alone does not interrupt a blocking recv. Keep
    the connected socket until completion and shut it down from the watcher.
    No shared connection, model unload, or cancellation of another request.
    """
    target = urlsplit(url)
    if target.scheme not in ("http", "https") or not target.hostname:
        raise ValueError("unsupported_model_url")
    connection_type = (http.client.HTTPSConnection if target.scheme == "https"
                       else http.client.HTTPConnection)
    options = {"timeout": timeout}
    if target.scheme == "https" and ssl_context is not None:
        options['context'] = ssl_context
    connection = connection_type(target.hostname, target.port, **options)
    finished = threading.Event()
    state = {"socket": None, "error": None}
    deadline = time.perf_counter() + timeout

    def check():
        if should_cancel():
            raise RequestCancelled("cancelled")
        if time.perf_counter() >= deadline:
            raise TimeoutError("model request deadline exceeded")

    def watch():
        while not finished.wait(0.05):
            try:
                check()
            except (RequestCancelled, TimeoutError) as exc:
                state["error"] = exc
                sock = state["socket"]
                if sock is not None:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                return

    watcher = threading.Thread(target=watch, name="rat-model-request", daemon=True)
    try:
        check()
        watcher.start()
        connection.connect()
        state["socket"] = connection.sock
        check()
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
        connection.request(method, path, body=json.dumps(payload).encode("utf-8") if payload is not None else None,
                           headers={"Content-Type": "application/json", **(headers or {})})
        with connection.getresponse() as reply:
            body = reply.read(max_body_bytes + 1)
            if len(body) > max_body_bytes:
                raise ValueError('response_too_large')
            check()
            if not 200 <= reply.status < 300:
                raise RuntimeError(f"model_http_error:{reply.status}")
            return json.loads(body)
    except Exception:
        if state["error"] is not None:
            raise state["error"]
        raise
    finally:
        finished.set()
        connection.close()
        if watcher.ident is not None:
            watcher.join()
