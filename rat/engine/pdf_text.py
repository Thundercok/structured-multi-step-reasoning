"""Undo PDF layout in copied text before it reaches the translation model.

Text copied from a PDF keeps the page's line breaks, end-of-line hyphenation
and typographic ligatures. The local model translates line by line, so one
sentence split over three lines came back as three broken fragments. Only the
text sent to the model is cleaned; the captured source and its hash stay as
observed so verification still matches.
"""
import re

LIGATURES = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st', 'ﬆ': 'st'}
_LIST_ITEM = re.compile(r'^\s*(?:[-*•▪–—]|\d+[.)]|\[\d+\]|[A-Za-z][.)])\s+')


def clean_copied_text(text):
    """Return (text for the model, number of line breaks joined)."""
    for ligature, letters in LIGATURES.items():
        text = text.replace(ligature, letters)
    text = text.replace('­', '').replace('\r\n', '\n').replace('\r', '\n')
    joins = 0
    paragraphs = []
    for block in re.split(r'\n\s*\n', text):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
        merged = lines[0]
        for line in lines[1:]:
            if _LIST_ITEM.match(line):
                merged += '\n' + line
                continue
            joins += 1
            if re.search(r'[A-Za-zÀ-ỹ]-$', merged) and line[:1].islower():
                merged = merged[:-1] + line  # "com-" + "plex" -> "complex"
            else:
                merged += ' ' + line
        paragraphs.append(merged)
    return '\n\n'.join(paragraphs), joins
