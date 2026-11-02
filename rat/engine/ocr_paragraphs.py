"""Conservative, observable OCR soft-wrap joining; no model and no text repair."""
import hashlib
import re

POLICY = 'aligned-soft-wrap-v1'
_LIST = re.compile(r'^\s*(?:[-*•▪–—]|\d+[.)]|[A-Za-z][.)])\s+')
_STRUCTURED = re.compile(r'[`{}=<>]|https?://|\t| {3,}')


def apply_line_joins(raw, indexes):
    lines = raw.split('\n')
    selected = set(indexes)
    if any(type(i) is not int or i < 0 or i >= len(lines)-1 for i in selected):
        raise ValueError('ocr_join_invalid')
    return ''.join(line + ((' ' if i in selected else '\n') if i < len(lines)-1 else '')
                   for i, line in enumerate(lines))


def prepare_ocr_text(tokens):
    """Preserve OCR order/characters; join only nearby, aligned prose lines.

    Lists, code, headings, columns, paragraph gaps and uncertain geometry keep
    their line breaks. This is deliberately not general document layout analysis.
    """
    rows = [token for token in tokens if token.get('text', '').strip()]
    raw = '\n'.join(token['text'].strip() for token in rows)
    joins = []
    for index, (before, after) in enumerate(zip(rows, rows[1:])):
        left, right = before['text'].strip(), after['text'].strip()
        if (len(left) < 12 or not any(c.isalpha() for c in left)
                or not any(c.isalpha() for c in right)
                or left.endswith(('.', '!', '?', ':', ';', '-', '。', '！', '？', '：', '；'))
                or _LIST.match(left) or _LIST.match(right)
                or _STRUCTURED.search(left) or _STRUCTURED.search(right)):
            continue
        try:
            ax, ay, ar, ab = before['bbox']
            bx, by, br, bb = after['bbox']
            height, next_height = ab-ay, bb-by
            aligned = abs(ax-bx) <= max(8, height*0.8)
            similar = height > 0 and 0.65*height <= next_height <= 1.5*height
            nearby = -0.15*height <= by-ab <= 1.2*height
            if aligned and similar and nearby and ar > ax and br > bx:
                joins.append(index)
        except (KeyError, TypeError, ValueError):
            continue
    text = apply_line_joins(raw, joins)
    return text, raw, {'policy': POLICY, 'joined_line_indexes': joins,
        'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
        'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
