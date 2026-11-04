"""What the translation card says, built only from what the translator reported."""
from __future__ import annotations

from typing import Any, Dict, List

LANGUAGE_NAMES = {
    "en": "Tiếng Anh", "vi": "Tiếng Việt", "zh": "Tiếng Trung", "ja": "Tiếng Nhật", "ko": "Tiếng Hàn",
    "fr": "Tiếng Pháp", "de": "Tiếng Đức", "es": "Tiếng Tây Ban Nha", "ru": "Tiếng Nga",
}
PROVIDER_LABELS = {
    "offline_argos": "Dịch trên máy",
    "google_gtx": "Dịch qua Google",
    "google": "Dịch qua Google",
    "mymemory": "Dịch qua MyMemory",
    "deepl": "Dịch qua DeepL",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, (code or "").upper() or "Tự nhận")


def method_line(result: Dict[str, Any]) -> str:
    """One line on how this text was translated. A fact the result does not report is left out."""
    parts: List[str] = []
    for provider in (result.get("provider") or "").split(", "):
        if provider == "same_language":
            parts.append("Đoạn này đã cùng ngôn ngữ, Chuột giữ nguyên")
        elif provider:
            label = PROVIDER_LABELS.get(provider, f"Dịch qua {provider}")
            if label not in parts:
                parts.append(label)
    if result.get("glossary_terms"):
        parts.append(f"giữ {result['glossary_terms']} thuật ngữ")
    if result.get("line_joins"):
        parts.append(f"nối {result['line_joins']} dòng bị ngắt")
    if result.get("status") == "partial":
        parts.append("còn đoạn chưa dịch được")
    parts.extend(result.get("warnings") or [])
    return " · ".join(parts)


def translation_card(result: Dict[str, Any]) -> Dict[str, Any]:
    source, target = result.get("source_lang", "auto"), result.get("target_lang", "vi")
    return {
        "text": result.get("text", ""),
        "source": source,
        "target": target,
        "direction": f"{language_name(source)} → {language_name(target)}",
        "sourceText": result.get("source_text", ""),
        "method": method_line(result),
    }
