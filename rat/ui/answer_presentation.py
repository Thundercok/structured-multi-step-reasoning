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
            output.append('<code style="font-family:Menlo,monospace;font-size:12px;background-color:' + code_bg + '">&nbsp;' + escape(part[1:-1]) + '&nbsp;</code>')
        else:
            part = escape(part)
            part = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', part)
            part = re.sub(r'__(.+?)__', r'<b>\1</b>', part)
            part = re.sub(r'(?<!\*)\*(?!\s|\*)(.+?)(?<!\s|\*)\*(?!\*)', r'<i>\1</i>', part)
            output.append(part)
    return ''.join(output)


def _split_pipe_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith('|'):
        stripped = stripped[1:]
    if stripped.endswith('|'):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split('|')]


def _is_table_separator(line: str, expected_cols: int) -> bool:
    if '|' not in line:
        return False
    cells = _split_pipe_row(line)
    if len(cells) < 2 or len(cells) != expected_cols:
        return False
    return all(bool(re.match(r'^:?-{2,}:?$', cell)) for cell in cells)


def _table_alignments(sep_line: str) -> list[str]:
    aligns = []
    for cell in _split_pipe_row(sep_line):
        if cell.startswith(':') and cell.endswith(':'):
            aligns.append('center')
        elif cell.endswith(':'):
            aligns.append('right')
        else:
            aligns.append('left')
    return aligns


@lru_cache(maxsize=8)
def answer_html(text: str, dark: bool = False) -> str:
    """Render paragraphs, headings, lists, blockquotes, tables and fenced code safely."""
    out, paragraph, code, quote, table_lines = [], [], [], [], []
    fence = None
    fence_lang = ''
    code_bg = '#333b2f' if dark else '#eff3e9'
    code_card_bg = '#2c3428' if dark else '#f2f5ed'
    border_col = '#3d4739' if dark else '#d3dcc9'
    quote_border_col = '#4e6343' if dark else '#bfd1b2'
    accent_col = '#a6c293' if dark else '#4f6740'
    quote_bg = '#283024' if dark else '#f3f7ee'
    quote_ink = '#d4dcd0' if dark else '#3e4b38'

    def spacer(px: int = 8) -> str:
        return f'<p style="margin-top:0;margin-bottom:{px}px;font-size:2px;">&nbsp;</p>'

    def render_code_card(lines: list[str], lang_label: str = '') -> str:
        lang_prefix = ''
        if lang_label:
            safe_lang = escape(lang_label.upper()[:24])
            lang_prefix = (
                f'<span style="font-family:Menlo,monospace;font-size:10px;'
                f'font-weight:600;color:{accent_col};">{safe_lang}</span><br>'
            )
        body = escape('\n'.join(lines))
        return (
            f'<table width="100%" bgcolor="{code_card_bg}" cellspacing="0" cellpadding="9" border="1" '
            f'style="border-collapse:collapse;border-color:{border_col};">'
            f'<tr><td>{lang_prefix}'
            f'<pre style="white-space:pre-wrap;font-family:Menlo,monospace;font-size:12px;'
            f'margin:3px 0 0 0;">{body}</pre></td></tr></table>'
            + spacer(10)
        )

    if _bare_python_source(text):
        return render_code_card(text.splitlines(), 'python')

    def flush_paragraph():
        if paragraph:
            out.append('<p style="margin-top:0;margin-bottom:12px;line-height:145%">' + '<br>'.join(_inline(line, code_bg) for line in paragraph) + '</p>')
            paragraph.clear()

    def flush_quote():
        if quote:
            inner = '<br>'.join(_inline(line, code_bg) for line in quote)
            out.append(
                f'<table width="100%" bgcolor="{quote_bg}" cellspacing="0" cellpadding="8" border="1" '
                f'style="border-collapse:collapse;border-color:{quote_border_col};">'
                f'<tr><td style="color:{quote_ink};line-height:145%;">'
                f'<span style="color:{accent_col};font-weight:600;">▎</span>&nbsp;{inner}</td></tr></table>'
                + spacer(10)
            )
            quote.clear()

    def flush_table():
        if not table_lines:
            return
        if len(table_lines) >= 2:
            headers = _split_pipe_row(table_lines[0])
            if len(headers) >= 2 and _is_table_separator(table_lines[1], len(headers)):
                aligns = _table_alignments(table_lines[1])
                rows_html = []
                th_cells = ''.join(
                    f'<th align="{aligns[i]}" style="color:{accent_col};font-size:12px;font-weight:600;"><b>{_inline(cell, code_bg)}</b></th>'
                    for i, cell in enumerate(headers)
                )
                rows_html.append(f'<tr>{th_cells}</tr>')
                for raw_row in table_lines[2:]:
                    cells = _split_pipe_row(raw_row)
                    if len(cells) < len(headers):
                        cells.extend([''] * (len(headers) - len(cells)))
                    else:
                        cells = cells[:len(headers)]
                    td_cells = ''.join(
                        f'<td align="{aligns[i]}" style="font-size:13px;">{_inline(cell, code_bg)}</td>'
                        for i, cell in enumerate(cells)
                    )
                    rows_html.append(f'<tr>{td_cells}</tr>')
                out.append(
                    f'<table width="100%" cellspacing="0" cellpadding="7" border="1" '
                    f'style="border-collapse:collapse;border-color:{border_col};">'
                    + ''.join(rows_html) + '</table>'
                    + spacer(10)
                )
                table_lines.clear()
                return
        # Fallback if pipe lines were not a Markdown table
        paragraph.extend(table_lines)
        table_lines.clear()
        flush_paragraph()

    def flush_all():
        flush_table()
        flush_quote()
        flush_paragraph()

    def flush_code():
        nonlocal fence_lang
        out.append(render_code_card(code, fence_lang))
        code.clear()
        fence_lang = ''

    for line in text.splitlines():
        stripped = line.strip()
        marker = re.match(r'^(`{3,}|~{3,})(.*)$', stripped)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence) and not marker.group(2).strip():
                flush_code()
                fence = None
            else:
                code.append(line)
            continue

        if marker:
            flush_all()
            fence = marker.group(1)
            fence_lang = marker.group(2).strip().split()[0] if marker.group(2).strip() else ''
            continue

        if not stripped:
            flush_all()
            continue

        if '|' in stripped and (table_lines or stripped.startswith('|') or stripped.count('|') >= 2):
            flush_quote()
            flush_paragraph()
            table_lines.append(stripped)
            continue
        elif table_lines:
            flush_table()

        if quote_match := re.match(r'^>\s?(.*)$', stripped):
            flush_paragraph()
            quote.append(quote_match.group(1))
            continue
        elif quote:
            flush_quote()

        if re.match(r'^(?:-{3,}|\*{3,}|_{3,})$', stripped):
            flush_all()
            out.append(f'<table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;margin-bottom:10px;"><tr><td height="1" bgcolor="{border_col}"></td></tr></table>')
        elif heading := re.match(r'^#{1,6}\s+(.+)$', stripped):
            flush_all()
            level = len(stripped.split(' ', 1)[0])
            px = 16 if level <= 2 else 14
            margin = 14 if out else 2
            out.append(f'<p style="font-size:{px}px;font-weight:600;margin-top:{margin}px;margin-bottom:6px">' + _inline(heading.group(1), code_bg) + '</p>')
        elif item := re.match(r'^(\s*)([-+*]|\d+[.)])\s+(.+)$', line):
            flush_all()
            indent = min(36, len(item.group(1)) * 3)
            marker_text = '•' if item.group(2) in '-+*' else item.group(2)
            out.append(f'<p style="margin-top:0;margin-bottom:6px;margin-left:{12 + indent}px;text-indent:-12px;line-height:145%">' + escape(marker_text) + ' ' + _inline(item.group(3), code_bg) + '</p>')
        else:
            paragraph.append(line)

    flush_all()
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

        # Extract section/heading strictly from authentic metadata; never default to 'Abstract'.
        raw_section = (
            source.get('section')
            or source.get('section_name')
            or source.get('section_title')
            or source.get('heading')
            or source.get('toc_item')
            or (provenance.get('section') if isinstance(provenance, dict) else None)
            or (provenance.get('section_name') if isinstance(provenance, dict) else None)
            or (provenance.get('section_title') if isinstance(provenance, dict) else None)
            or (provenance.get('heading') if isinstance(provenance, dict) else None)
        )
        section = str(raw_section).strip() if (raw_section and isinstance(raw_section, str) and raw_section.strip()) else ''

        if page is not None and page > 0:
            ref_label = f"Trang {page} · {section}" if section else f"Trang {page}"
            location_str = f"Trang PDF {page} · {section}" if section else f"Trang PDF {page}"
        else:
            ref_label = "Chưa xác định trang"
            location_str = "Chưa xác định trang"

        rows.append({'title': str(title), 'page': page or 0,
                     'section': section,
                     'label': ref_label,
                     'location': location_str,
                     'readScope': read_scope,
                     'path': resolved_path if matches else '',
                     'snippet': snippet if matches else '',
                     'canOpen': bool(matches and page and page <= page_count)})
    return rows
