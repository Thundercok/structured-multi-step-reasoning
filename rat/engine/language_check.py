"""Language detection and validation helpers for user queries and model outputs."""
from __future__ import annotations

import re

VIETNAMESE_DIACRITICS_REGEX = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)

CJK_REGEX = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
LATIN_REGEX = re.compile(
    r"[a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    r"ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]"
)

UNACCENTED_VN_KEYWORDS = {
    "app", "chinh", "anh", "quy", "che", "tai", "lieu", "bao", "cao",
    "chuot", "ban", "cho", "minh", "toi", "sao", "gi", "khong", "duoc",
}


def is_vietnamese(text: str) -> bool:
    """Return True if text appears to be Vietnamese (accented or common keywords)."""
    if not text:
        return False
    if VIETNAMESE_DIACRITICS_REGEX.search(text):
        return True
    words = {w.lower() for w in re.findall(r"\b\w+\b", text)}
    return len(words.intersection(UNACCENTED_VN_KEYWORDS)) >= 2


def is_mainly_cjk(text: str) -> bool:
    """Return True if text consists mainly of CJK characters."""
    if not text:
        return False
    cjk_count = len(CJK_REGEX.findall(text))
    if cjk_count == 0:
        return False
    latin_count = len(LATIN_REGEX.findall(text))
    total_letters = cjk_count + latin_count
    if total_letters > 0 and (cjk_count / total_letters) > 0.35:
        return True
    return cjk_count >= 5 and cjk_count > latin_count


ENGLISH_FUNCTION_WORDS = frozenset({
    "the", "is", "are", "was", "were", "a", "an", "of", "on", "in", "to", "for", "and", "that", "this", "it",
    "i", "you", "with", "based", "from", "have", "has", "not", "don't", "can", "be", "by", "or", "as",
})
_CODE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)
# What an answer quotes from a file says nothing about the language it is written in.
_QUOTED = re.compile(r'"[^"]*"|“[^”]*”|\([^)]*\)')


def reads_as_english(text: str) -> bool:
    """True for English prose, even with Vietnamese terms quoted in it. Code does not count."""
    prose = _QUOTED.sub(" ", _CODE.sub(" ", text or ""))
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", prose.lower())
    if len(words) < 4:
        return False
    english = sum(word in ENGLISH_FUNCTION_WORDS for word in words)
    marked = sum(bool(VIETNAMESE_DIACRITICS_REGEX.search(word)) for word in words)
    return english >= 2 and english > marked
