"""
rat.engine.web_reader — Lightweight web reader & summarizer.
Zero heavy browser dependencies; pure Python with urllib & httpx fallback.
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def extract_url(text: str) -> Optional[str]:
    """Extract the first HTTP/HTTPS URL found in text."""
    match = URL_PATTERN.search(text.strip())
    if match:
        url = match.group(0).rstrip(".,;!?:)")
        return url
    return None


def fetch_web_summary(url_or_text: str, timeout: float = 6.0) -> Dict[str, Any]:
    """Fetch URL and extract title, domain, meta description, and clean bullet summary."""
    target_url = extract_url(url_or_text) or url_or_text.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        return {
            "visual_type": "web",
            "url": target_url,
            "domain": "",
            "title": "URL không hợp lệ",
            "summary": "Vui lòng nhập đường dẫn web bắt đầu bằng http:// hoặc https://",
            "bullets": [],
            "status": "error",
            "error_message": "invalid_url",
        }

    parsed = urlparse(target_url)
    domain = parsed.netloc or parsed.path

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    }

    raw_html = ""
    try:
        # Prefer httpx if available
        import httpx
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(target_url)
            resp.raise_for_status()
            raw_html = resp.text
    except Exception:
        # Fallback to urllib.request
        try:
            import urllib.request
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
                raw_html = raw_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            return {
                "visual_type": "web",
                "url": target_url,
                "domain": domain,
                "title": f"Không thể tải trang ({domain})",
                "summary": f"Chuột không mở được liên kết này: {e}",
                "bullets": [],
                "status": "error",
                "error_message": str(e),
            }

    # Extract <title>
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    title = html.unescape(title_match.group(1).strip()) if title_match else domain

    # Extract meta description
    meta_desc = ""
    desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', raw_html, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']', raw_html, re.IGNORECASE)
    if desc_match:
        meta_desc = html.unescape(desc_match.group(1).strip())

    # Strip scripts, styles, comments
    cleaned = re.sub(r"<(script|style|noscript|header|footer|nav)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [re.sub(r"\s+", " ", line).strip() for line in cleaned.splitlines()]
    meaningful_paras = [l for l in lines if len(l) > 40 and not l.startswith("{") and not l.startswith("function")]

    bullets = []
    if meta_desc and len(meta_desc) > 20:
        bullets.append(meta_desc)

    for p in meaningful_paras:
        if len(bullets) >= 3:
            break
        if p not in bullets and not any(p in b or b in p for b in bullets):
            bullets.append(p[:240] + ("…" if len(p) > 240 else ""))

    if not bullets and meaningful_paras:
        bullets = [meaningful_paras[0][:250]]

    summary_text = "\n".join(f"• {b}" for b in bullets) if bullets else (meta_desc or "Đã tải trang thành công.")

    return {
        "visual_type": "web",
        "url": target_url,
        "domain": domain,
        "title": title,
        "summary": summary_text,
        "bullets": bullets,
        "status": "success",
        "error_message": "",
    }
