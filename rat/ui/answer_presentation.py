"""Small, inert answer formatting and public-reference labels for Qt Quick.

This module does not execute Markdown, load resources, or infer citations.
The controller retains the original answer for full-copy and conversation history.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from html import escape
from pathlib import Path
import re


@lru_cache(maxsize=8)
def _bare_python_source(text: str) -> bool:
    """Recognize complete unfenced Python definitions without executing them."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return False
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               for node in tree.body)


def answer_starts_with_code(text: str) -> bool:
    if _bare_python_source(text):
        return True
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or re.match(r'^#{1,6}\s+', stripped):
            continue
        return bool(re.match(r'^(`{3,}|~{3,})', stripped))
    return False


def answer_excerpt(text: str, limit: int = 360) -> str:
    """Opening prose or first code lines, never a generated summary."""
    if _bare_python_source(text):
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        excerpt = '\n'.join(lines[:3]) + ('…' if len(lines) > 3 else '')
        return excerpt[:limit].rstrip() + '…' if len(excerpt) > limit else excerpt
    paragraph = []
    code_lines = None
    for line in text.splitlines():
        stripped = line.strip()
        if code_lines is not None:
            if re.match(r'^(`{3,}|~{3,})', stripped):
                break
            if stripped:
                code_lines.append(line.rstrip())
                if len(code_lines) > 3:
                    break
            continue
        if not stripped:
            continue
        if re.match(r'^#{1,6}\s+', stripped) and not paragraph:
            continue
        if re.match(r'^(`{3,}|~{3,})', stripped):
            if not paragraph:
                code_lines = []
                continue
            break
        paragraph.append(re.sub(r'^\s*[-+*]\s+', '', stripped))
    if code_lines is not None:
        excerpt = '\n'.join(code_lines[:3]) + ('…' if len(code_lines) > 3 else '')
    else:
        excerpt = '\n'.join(paragraph)
    excerpt = re.sub(r'`([^`]+)`', r'\1', excerpt)
    excerpt = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: m.group(1) or m.group(2), excerpt)
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rsplit(' ', 1)[0].rstrip() + '…'
    return excerpt


@lru_cache(maxsize=8)
def page_reading_text(text: str) -> str:
    """Join only obvious prose continuations; keep source text separately.

    Each change replaces one newline with one space. Headings, new bullets,
    paragraph boundaries, indented code and likely formulas/tables stay intact.
    This is a conservative reading aid, not PDF layout reconstruction.
    """
    if '\r' in text or '```' in text or '~~~' in text:
        return text
    lines = text.splitlines(keepends=True)
    result = []
    for index, line in enumerate(lines):
        current = line.strip()
        following = lines[index + 1].strip() if index + 1 < len(lines) else ''
        pair = line + (lines[index + 1] if index + 1 < len(lines) else '')
        protected = (re.search(r'[=<>∑∫∀∃¬∧∨→↔|{}\[\]\t]', pair)
                     or re.search(r'\S {2,}\S', pair)
                     or line.startswith('    ')
                     or (index + 1 < len(lines) and lines[index + 1].startswith('    ')))
        join = (line.endswith('\n') and len(current) >= 38 and following
                and following[0].islower() and current[-1] not in '.!?:;'
                and not protected)
        result.append(line[:-1] + ' ' if join else line)
    return ''.join(result)


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
    if _bare_python_source(text):
        return ('<pre style="white-space:pre-wrap;font-family:Menlo,monospace;font-size:12px;'
                'background-color:' + code_bg + ';margin-top:10px;margin-bottom:16px">'
                + escape(text) + '</pre>')

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
        resolved_path = resolved(path) if path else ''
        matches = bool(resolved_path and selected and resolved_path == selected)
        read_scope = ''
        if source.get('truncated') is True:
            chars = source.get('read_chars')
            read_scope = 'Trích đoạn'
            if type(chars) is int and chars > 0:
                read_scope += ' · ' + f'{chars:,}'.replace(',', '.') + ' ký tự'
        raw_snippet = source.get('excerpt') or source.get('snippet') or ''
        snippet = str(raw_snippet)[:300] if isinstance(raw_snippet, str) else ''
        rows.append({'title': str(title), 'page': page or 0,
                     'location': f'Trang PDF {page}' if page else 'Chưa có vị trí trang',
                     'readScope': read_scope,
                     'path': resolved_path if matches else '',
                     'snippet': snippet if matches else '',
                     'canOpen': bool(matches and page and page <= page_count)})
    return rows
