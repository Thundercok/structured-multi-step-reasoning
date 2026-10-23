"""Small, inert answer formatting and public-reference labels for Qt Quick.

This module does not execute Markdown, load resources, or infer citations.
The controller retains the original answer for full-copy and conversation history.
"""
from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path
import re


def answer_excerpt(text: str, limit: int = 360) -> str:
    """Opening prose only, never a generated summary; full answer stays unchanged."""
    paragraph = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if re.match(r'^#{1,6}\s+', stripped) and not paragraph:
            continue
        if re.match(r'^(`{3,}|~{3,})', stripped):
            break
        paragraph.append(re.sub(r'^\s*(?:[-+*]|\d+[.)])\s+', '', stripped))
    excerpt = ' '.join(paragraph)
    excerpt = re.sub(r'`([^`]+)`', r'\1', excerpt)
    excerpt = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: m.group(1) or m.group(2), excerpt)
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rsplit(' ', 1)[0].rstrip() + '…'
    return excerpt


def _inline(text: str, code_bg: str) -> str:
    # Only these explicit inline constructs become markup. URLs, raw HTML and
    # Markdown images remain text; no model-authored resource gets loaded.
    parts = re.split(r'(`[^`\n]+`)', text)
    output = []
    for part in parts:
        if part.startswith('`') and part.endswith('`'):
            output.append('<code style="font-family:Menlo,monospace;font-size:12px;background-color:' + code_bg + '">' + escape(part[1:-1]) + '</code>')
        else:
            part = escape(part)
            part = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', part)
            part = re.sub(r'__(.+?)__', r'<b>\1</b>', part)
            output.append(part)
    return ''.join(output)


@lru_cache(maxsize=8)
def answer_html(text: str, dark: bool = False) -> str:
    """Render paragraphs, headings, lists and fenced code, escaping everything else."""
    out, paragraph, code = [], [], []
    fence = None
    code_bg = '#333b2f' if dark else '#eff3e9'

    def flush():
        if paragraph:
            out.append('<p style="margin-top:0;margin-bottom:14px;line-height:145%">' + '<br>'.join(_inline(line, code_bg) for line in paragraph) + '</p>')
            paragraph.clear()

    def flush_code():
        out.append('<pre style="white-space:pre-wrap;font-family:Menlo,monospace;font-size:12px;background-color:' + code_bg + ';margin-top:10px;margin-bottom:16px">' + escape('\n'.join(code)) + '</pre>')
        code.clear()

    for line in text.splitlines():
        stripped = line.strip()
        marker = re.match(r'^(`{3,}|~{3,})(.*)$', stripped)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) and not marker.group(2).strip():
                flush_code()
                fence = None
            else:
                code.append(line)
        elif marker:
            flush()
            fence = marker.group(1)
        elif not stripped:
            flush()
        elif heading := re.match(r'^#{1,6}\s+(.+)$', stripped):
            flush()
            margin = 18 if out else 0
            out.append(f'<p style="font-size:16px;font-weight:600;margin-top:{margin}px;margin-bottom:8px">' + _inline(heading.group(1), code_bg) + '</p>')
        elif item := re.match(r'^(\s*)([-+*]|\d+[.)])\s+(.+)$', line):
            flush()
            indent = min(36, len(item.group(1)) * 3)
            marker_text = '•' if item.group(2) in '-+*' else item.group(2)
            out.append(f'<p style="margin-top:0;margin-bottom:6px;margin-left:{12 + indent}px;text-indent:-12px;line-height:145%">' + escape(marker_text) + ' ' + _inline(item.group(3), code_bg) + '</p>')
        else:
            paragraph.append(line)
    flush()
    if fence:
        flush_code()
    return ''.join(out)


def source_rows(sources, selected_path=None, page_count=0):
    """Show explicit public metadata; a matching selected PDF enables page reading.

    A runtime reference is a reference, not evidence that its claim is correct.
    Missing page numbers never default to 1.
    """
    def resolved(path):
        try:
            return str(Path(path).resolve()) if path else ''
        except (OSError, ValueError, RuntimeError):
            return ''

    rows = []
    selected = resolved(selected_path)
    for source in sources or []:
        if hasattr(source, 'to_dict'):
            source = source.to_dict()
        if not isinstance(source, dict):
            continue
        path = source.get('path') or source.get('file_path') or ''
        if not isinstance(path, str):
            path = ''
        page = source.get('page_num', source.get('page', source.get('page_number')))
        if type(page) is not int or page < 1:
            page = None
        provenance = source.get('provenance')
        title = source.get('title') or source.get('filename') or source.get('file_name') or source.get('name') or (provenance.get('title') if isinstance(provenance, dict) else None) or Path(path).name or source.get('source_id') or 'Nguồn'
        matches = bool(path and selected and resolved(path) == selected)
        rows.append({'title': str(title), 'page': page or 0,
                     'location': f'Trang PDF {page}' if page else 'Chưa có vị trí trang',
                     'canOpen': bool(matches and page and page <= page_count)})
    return rows
