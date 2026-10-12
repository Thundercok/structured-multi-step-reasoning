"""
utils.py — URL normalisation, safe filenames, and robots.txt enforcement.
"""

import hashlib
import os
import threading
from urllib.parse import urldefrag, urlparse
from urllib.robotparser import RobotFileParser

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def normalize(url: str) -> str:
    """Strip fragment and trailing slash so equivalent URLs deduplicate."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(path=path).geturl()


def safe_filename(url: str, ext: str = "") -> str:
    """
    Build a collision-free filename from *url*.

    Uses a 12-char MD5 prefix so two images both named 'logo.png'
    from different domains never overwrite each other.
    """
    digest = hashlib.md5(url.encode()).hexdigest()[:12]
    base = os.path.basename(urlparse(url).path) or "file"
    name, original_ext = os.path.splitext(base)
    return f"{name}_{digest}{ext or original_ext or '.bin'}"


def url_folder(output_root: str, url: str) -> str:
    """
    Return a deterministic output folder for *url*:
        <output_root>/<domain>/<md5(url)[:10]>/
    """
    domain = urlparse(url).netloc.replace(".", "_")
    digest = hashlib.md5(url.encode()).hexdigest()[:10]
    return os.path.join(output_root, domain, digest)


# ---------------------------------------------------------------------------
# Robots.txt cache
# ---------------------------------------------------------------------------

_robots: dict[str, RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def can_fetch(url: str, *, respect: bool, agent: str = "*") -> bool:
    """
    Return True if *agent* is allowed to fetch *url*.

    Results are cached per robots.txt URL. An unreachable robots.txt
    is treated as fully permissive.
    """
    if not respect:
        return True

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    with _robots_lock:
        if robots_url not in _robots:
            rp = RobotFileParser(robots_url)
            try:
                rp.read()
            except Exception:
                rp = None  # type: ignore[assignment]
            _robots[robots_url] = rp

    rp = _robots[robots_url]
    return rp is None or rp.can_fetch(agent, url)
