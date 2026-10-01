"""
rat.engine.context_parser — Natural Language context & intent parser for non-tech users.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple


def remove_accents(text: str) -> str:
    """Normalize and strip Vietnamese diacritics."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower()


# Stopwords in normalized unaccented form.
# IMPORTANT: Do NOT add Vietnamese content words that form academic compound phrases.
# e.g. "bai"+"tap" = "bài tập", "de"+"thi" = "đề thi", "bien"+"ban" = "biên bản" — must survive.
STOPWORDS: Set[str] = {
    # Vietnamese (function words / fillers only — NO content words)
    "tim", "kiem", "cho", "toi", "tao", "minh", "gium", "ho", "cai", "con",
    "tep", "van", "nay", "do", "no", "kia", "nao",
    "o", "dau", "trong", "voi", "co", "chua", "nhac", "den", "ve",
    "nhe", "nha", "oi", "xem", "lai", "duoc", "khong", "cu", "vua",
    "chu", "noi", "va", "cua", "cac",
    "nhung", "mot", "la", "ma", "nhu", "ra", "vao", "theo",
    # Temporal fillers (should NOT become search keywords)
    "hoi", "dao", "dot", "luc", "khoang", "vao",
    # English
    "find", "search", "get", "show", "me", "the", "a", "an", "file", "document",
    "files", "documents", "that", "which", "has", "contains", "about", "from",
    "where", "is", "in", "on", "please", "can", "you", "my", "of", "for", "with"
}

# Vietnamese compound phrases that must be kept as single keywords.
# Protects multi-word terms whose individual tokens might look like stopwords or noise.
PROTECTED_COMPOUNDS: Set[str] = {
    # Academic subjects & tasks
    "bai tap", "bai tap lon", "de thi", "kiem tra", "bao cao", "do an",
    "khoa luan", "tot nghiep", "giai tich", "dai so", "xac suat", "thong ke",
    "lap trinh", "co so du lieu", "tri tue nhan tao", "xu ly anh",
    "mang may tinh", "he dieu hanh", "cong nghe phan mem",
    "ky thuat dien", "vat ly", "hoa hoc", "sinh hoc", "kinh te",
    "quan tri", "ke toan", "tai chinh", "de cuong", "on thi", "on tap",
    # Administrative / work documents
    "bien ban", "ke hoach", "de an", "noi dung", "tong ket",
    "bien ban hop", "hoi nghi", "hoi thao",
    # Common teacher references
    "thay dung", "co dung", "thay hung", "co lan", "co thao",
    # Misc academic
    "bai giang", "giao trinh", "tai lieu", "de cuong mon hoc",
}

# Type mappings
TYPE_PATTERNS: Dict[str, List[str]] = {
    # Word
    r"\b(word|docx?|van ban|soan thao)\b": [".docx", ".doc"],
    # PDF
    r"\b(pdf|scan|sach|giao trinh|ebook)\b": [".pdf"],
    # Excel / Spreadsheet
    r"\b(excel|xlsx?|csv|bang tinh|bang luong|thu chi|ke toan|tinh tien|so sach)\b": [".xlsx", ".xls", ".csv"],
    # PowerPoint
    r"\b(powerpoint|pptx?|slide|thuyet trinh|bai giang|presentation)\b": [".pptx", ".ppt"],
    # Image
    r"\b(hinh anh|anh|hinh|photo|image|picture|png|jpe?g|webp|screenshot|chup man hinh|cap man hinh|buc anh)\b": [".png", ".jpg", ".jpeg", ".webp"],
    # Code
    r"\b(code|ma nguon|python|script|py|javascript|js|typescript|ts|html|css|json|sql|sh)\b": [
        ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".yaml", ".yml", ".sh", ".sql"
    ],
    # Text / Notes
    r"\b(note|ghi chu|txt|markdown|md)\b": [".txt", ".md"]
}


class ParsedContext:
    """Represents the structured interpretation of a messy natural language query across OS facets."""

    def __init__(
        self,
        raw_query: str,
        keywords: List[str],
        extensions: Optional[List[str]] = None,
        excluded_extensions: Optional[List[str]] = None,
        excluded_keywords: Optional[List[str]] = None,
        date_min: Optional[float] = None,
        date_max: Optional[float] = None,
        time_desc: Optional[str] = None,
        file_type_desc: Optional[str] = None,
        source_app: Optional[str] = None,
        source_domain: Optional[str] = None,
        visual_concepts: Optional[List[str]] = None,
    ) -> None:
        self.raw_query = raw_query
        self.keywords = keywords
        self.extensions = extensions or []
        self.excluded_extensions = excluded_extensions or []
        self.excluded_keywords = excluded_keywords or []
        self.date_min = date_min
        self.date_max = date_max
        self.time_desc = time_desc
        self.file_type_desc = file_type_desc
        self.source_app = source_app
        self.source_domain = source_domain
        self.visual_concepts = visual_concepts or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "keywords": self.keywords,
            "extensions": self.extensions,
            "excluded_extensions": self.excluded_extensions,
            "excluded_keywords": self.excluded_keywords,
            "date_min": self.date_min,
            "date_max": self.date_max,
            "time_desc": self.time_desc,
            "file_type_desc": self.file_type_desc,
            "source_app": self.source_app,
            "source_domain": self.source_domain,
            "visual_concepts": self.visual_concepts,
        }


class ContextParser:
    """Extracts search constraints and intent from natural language queries."""

    @staticmethod
    def parse_temporal_context(query: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Detect temporal expressions and return (date_min, date_max, description).
        """
        now = datetime.datetime.now()
        today_start = datetime.datetime(now.year, now.month, now.day)
        today_end = today_start + datetime.timedelta(days=1, microseconds=-1)

        q_norm = remove_accents(query)

        # "hôm nay", "today"
        if re.search(r"\b(hom nay|today|ngay hom nay)\b", q_norm):
            return today_start.timestamp(), today_end.timestamp(), "Hôm nay"

        # "hôm qua", "yesterday"
        if re.search(r"\b(hom qua|yesterday|ngay hom qua)\b", q_norm):
            y_start = today_start - datetime.timedelta(days=1)
            y_end = today_start - datetime.timedelta(microseconds=1)
            return y_start.timestamp(), y_end.timestamp(), "Hôm qua"

        # "hôm kia", "ngay hom kia"
        if re.search(r"\b(hom kia|ngay hom kia)\b", q_norm):
            yk_start = today_start - datetime.timedelta(days=2)
            yk_end = today_start - datetime.timedelta(days=1, microseconds=1)
            return yk_start.timestamp(), yk_end.timestamp(), "Hôm kia"

        # "N ngày trước" / "N ngay qua"
        days_match = re.search(r"(\d+)\s*(ngay|day)s?\s*(truoc|qua|ago|recent)", q_norm)
        if days_match:
            n_days = int(days_match.group(1))
            start = now - datetime.timedelta(days=n_days)
            return start.timestamp(), now.timestamp(), f"{n_days} ngày gần đây"

        # "tuần này", "this week"
        if re.search(r"\b(tuan nay|this week)\b", q_norm):
            start_of_week = today_start - datetime.timedelta(days=now.weekday())
            return start_of_week.timestamp(), now.timestamp(), "Tuần này"

        # "tuần trước", "last week"
        if re.search(r"\b(tuan truoc|last week)\b", q_norm):
            start_of_current_week = today_start - datetime.timedelta(days=now.weekday())
            start_of_last_week = start_of_current_week - datetime.timedelta(days=7)
            end_of_last_week = start_of_current_week - datetime.timedelta(microseconds=1)
            return start_of_last_week.timestamp(), end_of_last_week.timestamp(), "Tuần trước"

        # "tháng này", "this month"
        if re.search(r"\b(thang nay|this month)\b", q_norm):
            start_of_month = datetime.datetime(now.year, now.month, 1)
            return start_of_month.timestamp(), now.timestamp(), "Tháng này"

        # "tháng trước", "last month"
        if re.search(r"\b(thang truoc|last month)\b", q_norm):
            first_day_current_month = datetime.datetime(now.year, now.month, 1)
            last_day_prev_month = first_day_current_month - datetime.timedelta(days=1)
            start_of_prev_month = datetime.datetime(last_day_prev_month.year, last_day_prev_month.month, 1)
            return start_of_prev_month.timestamp(), first_day_current_month.timestamp(), "Tháng trước"

        # Specific month: "tháng 7", "thang 7", "thang 12"
        month_match = re.search(r"\b(thang|month)\s*(\d{1,2})\b", q_norm)
        if month_match:
            month_num = int(month_match.group(2))
            if 1 <= month_num <= 12:
                # Default to current year if month is <= current month, otherwise last year
                target_year = now.year if month_num <= now.month else now.year - 1
                start_dt = datetime.datetime(target_year, month_num, 1)
                if month_num == 12:
                    end_dt = datetime.datetime(target_year + 1, 1, 1)
                else:
                    end_dt = datetime.datetime(target_year, month_num + 1, 1)
                return start_dt.timestamp(), end_dt.timestamp(), f"Tháng {month_num}/{target_year}"

        # "mới đây", "gần đây", "recently"
        if re.search(r"\b(moi day|gan day|moi sua|moi tai|recently|recent)\b", q_norm):
            recent_start = now - datetime.timedelta(days=7)
            return recent_start.timestamp(), now.timestamp(), "Gần đây (7 ngày)"

        return None, None, None

    @staticmethod
    def parse_file_types(query: str) -> Tuple[List[str], Optional[str]]:
        """Detect intended file types."""
        q_norm = remove_accents(query)
        detected_extensions: List[str] = []
        detected_descriptions: List[str] = []

        for pattern, exts in TYPE_PATTERNS.items():
            if re.search(pattern, q_norm):
                for e in exts:
                    if e not in detected_extensions:
                        detected_extensions.append(e)
                desc = exts[0].replace(".", "").upper()
                if desc not in detected_descriptions:
                    detected_descriptions.append(desc)

        desc_str = ", ".join(detected_descriptions) if detected_descriptions else None
        return detected_extensions, desc_str

    @staticmethod
    def parse_exclusions(query: str) -> Tuple[List[str], List[str]]:
        """Detect excluded file extensions and excluded terms (e.g. 'không phải word', 'trừ pdf')."""
        q_norm = remove_accents(query)
        excluded_exts: List[str] = []
        excluded_kw: List[str] = []

        # Check for negation patterns like "không phải X", "khong lay X", "trừ X", "loại trừ X", "except X", "not X"
        neg_matches = re.finditer(r"\b(khong phai|khong lay|khong chua|tru|loai tru|except|not|without)\s+([\w\.\-]+)", q_norm)
        for m in neg_matches:
            target = m.group(2).strip()
            # Check if target matches an extension
            for pattern, exts in TYPE_PATTERNS.items():
                if re.search(pattern, target):
                    for e in exts:
                        if e not in excluded_exts:
                            excluded_exts.append(e)
            if target not in [e.replace(".", "") for e in excluded_exts]:
                excluded_kw.append(target)

        return excluded_exts, excluded_kw

    @staticmethod
    def parse_provenance_context(query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect OS provenance cues such as downloading application or source website.
        Returns: (source_app, source_domain)
        """
        q_norm = remove_accents(query)

        app_map = {
            r"\b(telegram)\b": "Telegram",
            r"\b(safari)\b": "Safari",
            r"\b(chrome|google chrome)\b": "Google Chrome",
            r"\b(slack)\b": "Slack",
            r"\b(discord)\b": "Discord",
            r"\b(zalo)\b": "Zalo",
            r"\b(mail|outlook|email)\b": "Mail",
            r"\b(messages|imessage)\b": "Messages",
        }

        domain_map = {
            r"\b(overleaf(\.com)?)\b": "overleaf.com",
            r"\b(github(\.com)?)\b": "github.com",
            r"\b(google drive|gg drive|drive\.google\.com)\b": "drive.google.com",
            r"\b(google docs|gg docs|docs\.google\.com)\b": "docs.google.com",
            r"\b(kaggle(\.com)?)\b": "kaggle.com",
            r"\b(dropbox(\.com)?)\b": "dropbox.com",
            r"\b(notion(\.so)?)\b": "notion.so",
        }

        # Check for trigger phrases: "từ X", "tải từ X", "download từ X", "qua X", "gửi qua X"
        prov_trigger = re.search(r"\b(tu|tai tu|download tu|qua|gui qua|nguon|from|via)\s+([\w\.\-]+)", q_norm)
        detected_app: Optional[str] = None
        detected_domain: Optional[str] = None

        for pattern, app_name in app_map.items():
            if re.search(pattern, q_norm):
                detected_app = app_name
                break

        for pattern, domain_name in domain_map.items():
            if re.search(pattern, q_norm):
                detected_domain = domain_name
                break

        # Fallback if specific domain mentioned directly after trigger
        if not detected_domain and prov_trigger:
            candidate = prov_trigger.group(2).lower()
            if candidate in ["overleaf", "github", "kaggle", "notion", "dropbox"]:
                detected_domain = f"{candidate}.com" if candidate != "notion" else "notion.so"

        return detected_app, detected_domain

    @staticmethod
    def parse_visual_context(query: str) -> Tuple[List[str], Optional[str]]:
        """
        Detect visual attributes, scene objects, and visual document types.
        Returns: (visual_concepts, description)
        """
        q_norm = remove_accents(query)
        concepts: List[str] = []

        visual_categories = {
            "receipt": [r"\b(hoa don|bien lai|receipt|invoice|bill)\b", "hóa đơn, biên lai"],
            "stamp": [r"\b(chu ky|dau moc|con dau|dong moc|signature|stamp)\b", "chữ ký, con dấu"],
            "chart": [r"\b(bieu do|do thi|chart|diagram|graph)\b", "biểu đồ, đồ thị"],
            "screenshot": [r"\b(chup man hinh|screenshot|cap man hinh)\b", "ảnh chụp màn hình"],
            "sunset": [r"\b(hoang hon|sunset|chieu ta|binh minh|sunrise)\b", "hoàng hôn, bình minh"],
            "beach": [r"\b(bai bien|bien|beach|ocean|cat trang)\b", "bãi biển, đại dương"],
            "pet": [r"\b(cho|meo|dog|cat|thu cung|pet|cun con|meo con)\b", "chó, mèo, thú cưng"],
            "vehicle": [r"\b(xe hoi|o to|car|xe may|motorcycle|oto)\b", "xe cộ, ô tô"],
            "food": [r"\b(mon an|food|do an|do uong|drink|nha hang)\b", "món ăn, ẩm thực"],
            "people": [r"\b(chan dung|nguoi|portrait|selfie|khuon mat)\b", "chân dung, người"],
        }

        desc_list: List[str] = []
        for cat_key, (pat, desc) in visual_categories.items():
            if re.search(pat, q_norm):
                concepts.append(cat_key)
                desc_list.append(desc)

        desc_str = ", ".join(desc_list) if desc_list else None
        return concepts, desc_str

    @classmethod
    def parse_query(cls, raw_query: str) -> ParsedContext:
        """Parse natural language query into structured context constraints & keywords."""
        cleaned_raw = raw_query.strip()
        if not cleaned_raw:
            return ParsedContext(raw_query="", keywords=[])

        date_min, date_max, time_desc = cls.parse_temporal_context(cleaned_raw)
        extensions, type_desc = cls.parse_file_types(cleaned_raw)
        excluded_extensions, excluded_keywords = cls.parse_exclusions(cleaned_raw)
        source_app, source_domain = cls.parse_provenance_context(cleaned_raw)
        visual_concepts, _ = cls.parse_visual_context(cleaned_raw)

        # If an extension is in excluded_extensions, remove it from extensions
        if excluded_extensions and extensions:
            extensions = [e for e in extensions if e not in excluded_extensions]

        # Extract core keywords by removing temporal words, type words, exclusion words, and stopwords
        q_norm = remove_accents(cleaned_raw)

        # Protect Vietnamese compound phrases before tokenization.
        # Replace matched compounds with underscore-joined tokens so they survive stopword filtering.
        q_protected = q_norm
        found_compounds: List[str] = []
        for compound in sorted(PROTECTED_COMPOUNDS, key=len, reverse=True):
            if compound in q_protected:
                placeholder = compound.replace(" ", "_")
                q_protected = q_protected.replace(compound, placeholder)
                found_compounds.append(compound)

        # Tokenize by non-alphanumeric
        tokens = re.findall(r"[\w\.\-]+", cleaned_raw)
        clean_keywords: List[str] = []

        # Add protected compound phrases as keywords directly
        for compound in found_compounds:
            clean_keywords.append(compound.replace("_", " "))

        exclusion_tokens = set([remove_accents(k).lower() for k in excluded_keywords])
        exclusion_markers = {"khong", "phai", "lay", "chua", "tru", "loai", "except", "not", "without"}

        for token in tokens:
            t_norm = remove_accents(token).lower()
            if len(t_norm) <= 1:
                continue
            if t_norm in STOPWORDS or t_norm in exclusion_markers or t_norm in exclusion_tokens:
                continue
            # Also check if token is part of detected temporal or type words
            if t_norm in [
                "hom", "qua", "nay", "kia", "tuan", "thang", "word", "docx", "doc",
                "excel", "xlsx", "xls", "csv", "pdf", "scan", "slide", "pptx", "ppt",
                "anh", "hinh", "code", "tep", "file"
            ]:
                continue
            if token not in clean_keywords:
                clean_keywords.append(token)

        # If all tokens were filtered out (e.g. user literally just typed "tìm file word hôm qua"),
        # keep keywords empty so we retrieve by time and type filters.
        return ParsedContext(
            raw_query=cleaned_raw,
            keywords=clean_keywords,
            extensions=extensions,
            excluded_extensions=excluded_extensions,
            excluded_keywords=excluded_keywords,
            date_min=date_min,
            date_max=date_max,
            time_desc=time_desc,
            file_type_desc=type_desc,
            source_app=source_app,
            source_domain=source_domain,
            visual_concepts=visual_concepts,
        )
