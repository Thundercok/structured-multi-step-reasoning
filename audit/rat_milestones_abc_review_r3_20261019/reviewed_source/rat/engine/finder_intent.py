"""Deterministic, zero-model natural-language intent parser for the progressive finder.

Produces an explicit FinderIntentPlan from raw Vietnamese/English user input without
importing heavy libraries, touching the network, or spawning subprocesses.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Any, Mapping, Optional
import unicodedata

from rat.engine.app_resolver import ApplicationCatalog, name_key


SLIDE_PRESENTATION_EXTENSIONS = (".pptx", ".ppt", ".key", ".odp")
SLIDE_ALLOWED_EXTENSIONS = (".pptx", ".ppt", ".key", ".odp", ".pdf")
SLIDE_INDICATORS = (
    "slide",
    "slides",
    "bai giang",
    "bài giảng",
    "bai_giang",
    "bai-giang",
    "baigiang",
    "lecture",
    "deck",
    "chuong",
    "chương",
    "buoi",
    "buổi",
)

REPORT_INDICATORS = (
    "bao cao",
    "báo cáo",
    "bao_cao",
    "bao-cao",
    "baocao",
    "report",
    "reports",
)


def _fold_ascii(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFD", text.casefold()).replace("đ", "d")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip()


def is_slide_row(row: Mapping[str, Any]) -> bool:
    """Explicit Slide rule:
    - Presentation extensions (.pptx, .ppt, .key, .odp) always qualify.
    - PDF files qualify ONLY if file_name, immediate parent folder, or summary contains a slide/lecture indicator.
    """
    ext = str(row.get("file_ext") or "").lower()
    if ext in SLIDE_PRESENTATION_EXTENSIONS:
        return True
    if ext != ".pdf":
        return False
    raw_path = str(row.get("file_path") or "")
    parent_name = ""
    if raw_path:
        parts = [p for p in re.split(r"[\\/]+", raw_path) if p]
        if len(parts) >= 2:
            parent_name = parts[-2]
    haystack = " ".join(
        _fold_ascii(val)
        for val in (str(row.get("file_name") or ""), parent_name, str(row.get("summary") or ""))
    )
    padded = f" {haystack} "
    for indicator in SLIDE_INDICATORS:
        ind_folded = _fold_ascii(indicator)
        if ind_folded and (ind_folded in haystack or f" {ind_folded} " in padded):
            return True
    return False


def is_report_row(row: Mapping[str, Any]) -> bool:
    """Explicit Report rule on row metadata for semantic/filter validation."""
    if row.get('_report_rule_matched'):
        return True
    haystack = " ".join(
        _fold_ascii(str(row.get(k) or ""))
        for k in ("file_name", "file_path", "summary", "content_text")
    )
    for indicator in REPORT_INDICATORS:
        ind_folded = _fold_ascii(indicator)
        if ind_folded and ind_folded in haystack:
            return True
    return False


@dataclass(frozen=True)
class FinderIntentPlan:
    raw_query: str
    action: str = "search"  # "search" | "open_app" | "negated_open"
    query_terms: str = ""
    resource_kind: str = "any"  # "any" | "file" | "slide" | "report" | "application"
    extensions: tuple[str, ...] = ()
    excluded_extensions: tuple[str, ...] = ()
    date_min: Optional[int] = None
    date_max: Optional[int] = None
    date_max_exclusive: Optional[int] = None
    date_field: str = "modified"  # "modified" | "created"
    sort: str = "relevance"  # "relevance" | "modified_desc"
    slide_rule: bool = False
    report_rule: bool = False
    target_app_query: str = ""
    needs_clarification: bool = False
    clarification_reason: str = ""
    conflicting_constraints: tuple[str, ...] = ()
    interpretation_chips: tuple[str, ...] = ()
    scope_note: str = ""

    @property
    def core_query(self) -> str:
        return self.query_terms

    @property
    def app_query(self) -> str:
        return self.target_app_query

    @property
    def file_exts(self) -> tuple[str, ...]:
        return self.extensions

    @property
    def applied_filters(self) -> tuple[str, ...]:
        return self.interpretation_chips

    @property
    def clarification_prompt(self) -> str:
        return self.clarification_reason

    @property
    def has_structured_constraints(self) -> bool:
        return bool(
            self.action in ("open_app", "negated_open")
            or self.resource_kind != "any"
            or self.extensions
            or self.excluded_extensions
            or self.date_min is not None
            or self.date_max is not None
            or self.date_max_exclusive is not None
            or self.sort != "relevance"
            or self.slide_rule
            or self.report_rule
            or self.needs_clarification
        )


_NEGATED_OPEN_PATTERNS = (
    r"^(?:xin\s+)?(?:đừng|dung|không|khong|chưa|chua|không\s+cần|khong\s+can|đừng\s+có|dung\s+co)\s+"
    r"(?:mở|mo|bật|bat|chạy|chay|khởi\s+động|khoi\s+dong)(?:\s+(?:ứng\s+dụng|ung\s+dung|app|game))?(?:\s+(.*))?$",
    r"^(?:please\s+)?(?:do\s+not|don't|dont|never)\s+(?:open|launch|start|run)(?:\s+(?:app|application))?(?:\s+(.*))?$",
)

_OPEN_PREFIX_PATTERNS = (
    r"^(?:hãy\s+|hay\s+|giúp\s+tôi\s+|giup\s+toi\s+|vui\s+lòng\s+|vui\s+long\s+)?"
    r"(?:mở|mo|bật|bat|khởi\s+động|khoi\s+dong|chạy|chay)\s+(?:ứng\s+dụng|ung\s+dung|app|game)(?:\s+(.*))?$",
    r"^(?:hãy\s+|hay\s+|giúp\s+tôi\s+|giup\s+toi\s+|vui\s+lòng\s+|vui\s+long\s+)?"
    r"(?:mở|mo|bật|bat|khởi\s+động|khoi\s+dong)(?:\s+(.*))?$",
    r"^(?:please\s+)?(?:open|launch)\s+(?:app|application)(?:\s+(.*))?$",
    r"^(?:please\s+)?(?:open|launch)(?:\s+(.*))?$",
)

_DOC_TARGET_STARTERS = (
    "file",
    "tep",
    "tệp",
    "tai lieu",
    "tài liệu",
    "slide",
    "slides",
    "bai giang",
    "bài giảng",
    "ban bao cao",
    "bản báo cáo",
    "bao cao",
    "báo cáo",
    "report",
    "pdf",
    "word",
    "docx",
    "excel",
    "xlsx",
    "pptx",
    "folder",
    "thu muc",
    "thư mục",
    "nguon",
    "nguồn",
)

_DOC_EXTENSIONS = (
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".key",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".md",
    ".rtf",
    ".odt",
    ".odp",
)


def _resolve_now(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now().astimezone()
    if now.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        return now.replace(tzinfo=local_tz)
    return now


def _extract_time_windows(
    text: str,
    now: datetime,
) -> tuple[str, list[tuple[str, int, int, str]]]:
    """Return (remaining_text, list of (window_id, start_ts, end_exclusive_ts, chip_label))."""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday = day_start - timedelta(days=day_start.weekday())
    prev_monday = this_monday - timedelta(days=7)
    next_monday = this_monday + timedelta(days=7)

    first_this_month = day_start.replace(day=1)
    if first_this_month.month == 1:
        first_prev_month = first_this_month.replace(year=first_this_month.year - 1, month=12)
    else:
        first_prev_month = first_this_month.replace(month=first_this_month.month - 1)
    if first_this_month.month == 12:
        first_next_month = first_this_month.replace(year=first_this_month.year + 1, month=1)
    else:
        first_next_month = first_this_month.replace(month=first_this_month.month + 1)

    create_verbs = (
        r"đã\s+tạo|da\s+tao|được\s+tạo|duoc\s+tao|tạo\s+lập|tao\s+lap|khởi\s+tạo|khoi\s+tao|"
        r"tạo|tao|làm|lam|viết|viet|"
        r"created|written|authored"
    )
    modify_verbs = (
        r"đã\s+sửa|da\s+sua|được\s+sửa|duoc\s+sua|sửa\s+đổi|sua\s+doi|chỉnh\s+sửa|chinh\s+sua|"
        r"đã\s+cập\s+nhật|da\s+cap\s+nhat|cập\s+nhật|cap\s+nhat|sửa|sua|"
        r"modified|updated|edited"
    )
    verb_prefix = (
        r"(?:(?:"
        + create_verbs
        + r"|"
        + modify_verbs
        + r")\s+)?"
        r"(?:(?:trong|vào|vao|ở|o|từ|tu|hồi|hoi|in|from|during)\s+)?"
    )

    specs = [
        (
            "last_week",
            verb_prefix + r"(?:tuần\s+trước|tuan\s+truoc|tuần\s+rồi|tuan\s+roi|tuần\s+qua|tuan\s+qua|last\s+week)\b",
            int(prev_monday.timestamp()),
            int(this_monday.timestamp()),
            f"Thời gian: Tuần trước ({prev_monday.strftime('%d/%m')}–{(this_monday - timedelta(days=1)).strftime('%d/%m')})",
        ),
        (
            "this_week",
            verb_prefix + r"(?:tuần\s+này|tuan\s+nay|trong\s+tuần|trong\s+tuan|this\s+week)\b",
            int(this_monday.timestamp()),
            int(next_monday.timestamp()),
            f"Thời gian: Tuần này ({this_monday.strftime('%d/%m')}–{(next_monday - timedelta(days=1)).strftime('%d/%m')})",
        ),
        (
            "yesterday",
            verb_prefix + r"(?:hôm\s+qua|hom\s+qua|ngày\s+hôm\s+qua|ngay\s+hom\s+qua|yesterday)\b",
            int((day_start - timedelta(days=1)).timestamp()),
            int(day_start.timestamp()),
            f"Thời gian: Hôm qua ({(day_start - timedelta(days=1)).strftime('%d/%m')})",
        ),
        (
            "today",
            verb_prefix + r"(?:hôm\s+nay|hom\s+nay|ngày\s+hôm\s+nay|ngay\s+hom\s+nay|today)\b",
            int(day_start.timestamp()),
            int((day_start + timedelta(days=1)).timestamp()),
            f"Thời gian: Hôm nay ({day_start.strftime('%d/%m')})",
        ),
        (
            "last_month",
            verb_prefix + r"(?:tháng\s+trước|thang\s+truoc|tháng\s+rồi|thang\s+roi|tháng\s+qua|thang\s+qua|last\s+month)\b",
            int(first_prev_month.timestamp()),
            int(first_this_month.timestamp()),
            f"Thời gian: Tháng trước ({first_prev_month.strftime('%m/%Y')})",
        ),
        (
            "this_month",
            verb_prefix + r"(?:tháng\s+này|thang\s+nay|this\s+month)\b",
            int(first_this_month.timestamp()),
            int(first_next_month.timestamp()),
            f"Thời gian: Tháng này ({first_this_month.strftime('%m/%Y')})",
        ),
    ]

    create_pat = r"\b(?:" + create_verbs + r")\b"
    found: list[tuple[str, int, int, str, str]] = []
    remaining = text
    for win_id, pattern, start_ts, end_ts, label in specs:
        m = re.search(pattern, remaining, flags=re.IGNORECASE)
        if m:
            matched_str = m.group(0)
            date_field = "created" if re.search(create_pat, matched_str, flags=re.IGNORECASE) else "modified"
            if date_field == "created":
                label = label.replace("Thời gian:", "Thời gian tạo:")
            found.append((win_id, start_ts, end_ts, label, date_field))
            remaining = (remaining[: m.start()] + " " + remaining[m.end() :]).strip()
    return re.sub(r"\s+", " ", remaining).strip(), found


def _looks_like_document_target(target: str) -> bool:
    folded = _fold_ascii(target)
    if not folded:
        return False
    if any(folded.endswith(ext) for ext in _DOC_EXTENSIONS):
        return True
    for starter in _DOC_TARGET_STARTERS:
        st_fold = _fold_ascii(starter)
        if folded == st_fold or folded.startswith(st_fold + " "):
            return True
    return False


def parse_finder_intent(
    raw_query: str,
    *,
    now: Optional[datetime] = None,
    catalog: Optional[ApplicationCatalog] = None,
) -> FinderIntentPlan:
    """Parse a Vietnamese/English finder query into a deterministic FinderIntentPlan."""
    cleaned = re.sub(r"\s+", " ", (raw_query or "").strip())
    if not cleaned:
        return FinderIntentPlan(raw_query=raw_query or "")

    # 1. Check negated open commands first ("đừng mở ...", "không mở ...")
    for neg_pat in _NEGATED_OPEN_PATTERNS:
        m = re.match(neg_pat, cleaned, flags=re.IGNORECASE)
        if m:
            target = (m.group(1) or "").strip(" .,!?:;\"'")
            chips = ["Hành động: Đã chặn mở ứng dụng (phủ định)"]
            if target:
                chips.append(f"Đối tượng: {target}")
            return FinderIntentPlan(
                raw_query=raw_query,
                action="negated_open",
                query_terms="",
                resource_kind="application",
                target_app_query=target,
                needs_clarification=False,
                clarification_reason="Câu lệnh có từ phủ định ('đừng/không mở'); hệ thống giữ nguyên và không tự động mở ứng dụng.",
                interpretation_chips=tuple(chips),
                scope_note="Không thực thi mở ứng dụng khi có từ phủ định.",
            )

    # 2. Check explicit app-open commands ("mở Liên Minh", "mở ứng dụng ...", "open ...")
    for idx, open_pat in enumerate(_OPEN_PREFIX_PATTERNS):
        m = re.match(open_pat, cleaned, flags=re.IGNORECASE)
        if m:
            explicit_app_word = idx in (0, 2)  # "mở ứng dụng ...", "open app ..."
            target = (m.group(1) or "").strip(" .,!?:;\"'")
            if not target:
                return FinderIntentPlan(
                    raw_query=raw_query,
                    action="open_app",
                    query_terms="",
                    resource_kind="application",
                    target_app_query="",
                    needs_clarification=True,
                    clarification_reason="Bạn muốn mở ứng dụng nào? Hãy nhập tên ứng dụng (ví dụ: mở Liên Minh).",
                    interpretation_chips=("Hành động: Mở ứng dụng", "Thiếu tên ứng dụng"),
                    scope_note="Cần chỉ rõ tên ứng dụng macOS trong danh mục để kiểm tra và khởi chạy.",
                )

            # Check if target looks like a document/slide/report query rather than an app
            catalog_matches = catalog.search(target, limit=5) if (catalog and name_key(target)) else ()
            if explicit_app_word or catalog_matches or not _looks_like_document_target(target):
                chips = ("Hành động: Mở ứng dụng", f"Ứng dụng: {target}")
                note = "Chỉ gõ để xem gợi ý; nhấn Enter hoặc nút Mở để kiểm tra gói .app và gửi yêu cầu mở tới macOS."
                return FinderIntentPlan(
                    raw_query=raw_query,
                    action="open_app",
                    query_terms=target,
                    resource_kind="application",
                    target_app_query=target,
                    needs_clarification=False,
                    interpretation_chips=chips,
                    scope_note=note,
                )
            # If user wrote e.g. "mở slide DSA sửa tuần trước", strip "mở" and parse as document search!
            cleaned = target
            break

    # 3. Parse time windows with injectable clock
    ref_now = _resolve_now(now)
    working, time_windows = _extract_time_windows(cleaned, ref_now)

    date_min: Optional[int] = None
    date_max: Optional[int] = None
    date_max_exclusive: Optional[int] = None
    date_field = "modified"
    needs_clarification = False
    clarification_reason = ""
    conflicting_constraints: tuple[str, ...] = ()
    chips: list[str] = []
    scope_notes: list[str] = []

    if len(time_windows) > 1:
        needs_clarification = True
        conflicting_constraints = tuple(label for _, _, _, label, _ in time_windows)
        clarification_reason = (
            "Điều kiện thời gian mâu thuẫn (nhiều mốc thời gian trong cùng câu). "
            "Vui lòng chọn một khoảng thời gian rõ ràng."
        )
        chips.append("Thời gian: Mâu thuẫn cần làm rõ")
    elif len(time_windows) == 1:
        _, start_ts, end_excl_ts, time_chip, win_date_field = time_windows[0]
        date_min = start_ts
        date_max_exclusive = end_excl_ts
        date_max = end_excl_ts - 1
        date_field = win_date_field
        chips.append(time_chip)

    # 4. Parse sort modifiers ("mới nhất", "gần nhất", "mới sửa", "latest", "newest")
    sort = "relevance"
    sort_pat = (
        r"\b(?:"
        r"mới\s+sửa\s+nhất|moi\s+sua\s+nhat|"
        r"sửa\s+gần\s+nhất|sua\s+gan\s+nhat|"
        r"cập\s+nhật\s+mới\s+nhất|cap\s+nhat\s+moi\s+nhat|"
        r"mới\s+nhất|moi\s+nhat|"
        r"gần\s+đây\s+nhất|gan\s+day\s+nhat|"
        r"gần\s+nhất|gan\s+nhat|"
        r"mới\s+sửa|moi\s+sua|"
        r"vừa\s+sửa|vua\s+sua|"
        r"most\s+recent|recently\s+modified|latest|newest"
        r")\b"
    )
    if re.search(sort_pat, working, flags=re.IGNORECASE):
        sort = "modified_desc"
        working = re.sub(sort_pat, " ", working, flags=re.IGNORECASE).strip()

    # 5. Parse resource kind / type rules (Slide, Report, explicit file extensions)
    slide_rule = False
    report_rule = False
    resource_kind = "any"
    extensions: list[str] = []

    slide_pat = (
        r"\b(?:"
        r"tài\s+liệu\s+slide|tai\s+lieu\s+slide|"
        r"file\s+slide|tệp\s+slide|tep\s+slide|"
        r"bài\s+giảng\s+slide|bai\s+giang\s+slide|"
        r"slides?|bài\s+giảng|bai\s+giang|lectures?|decks?|"
        r"thuyết\s+trình|thuyet\s+trinh|powerpoint|keynote"
        r")\b"
    )
    if re.search(slide_pat, working, flags=re.IGNORECASE):
        slide_rule = True
        resource_kind = "slide"
        working = re.sub(slide_pat, " ", working, flags=re.IGNORECASE).strip()

    report_pat = (
        r"\b(?:"
        r"các\s+bản\s+báo\s+cáo|cac\s+ban\s+bao\s+cao|"
        r"những\s+bản\s+báo\s+cáo|nhung\s+ban\s+bao\s+cao|"
        r"bản\s+báo\s+cáo|ban\s+bao\s+cao|"
        r"file\s+báo\s+cáo|tep\s+bao\s+cao|tệp\s+báo\s+cáo|"
        r"tài\s+liệu\s+báo\s+cáo|tai\s+lieu\s+bao\s+cao|"
        r"báo\s+cáo|bao\s+cao|reports?"
        r")\b"
    )
    if not slide_rule and re.search(report_pat, working, flags=re.IGNORECASE):
        report_rule = True
        resource_kind = "report"
        working = re.sub(report_pat, " ", working, flags=re.IGNORECASE).strip()

    # Check explicit format keywords when structured modifiers or explicit "file <ext>" is used
    ext_specs = [
        (r"\b(?:file\s+|tệp\s+|tep\s+)?\.?pdf\b", (".pdf",), "PDF"),
        (r"\b(?:file\s+|tệp\s+|tep\s+)?(?:word|docx?|\.docx?)\b", (".docx", ".doc"), "Word (.docx/.doc)"),
        (r"\b(?:file\s+|tệp\s+|tep\s+|bảng\s+tính\s+|bang\s+tinh\s+)?(?:excel|xlsx?|\.xlsx?)\b", (".xlsx", ".xls", ".csv"), "Bảng tính (.xlsx/.xls/.csv)"),
        (r"\b(?:file\s+|tệp\s+|tep\s+)?(?:\.pptx?|pptx?)\b", (".pptx", ".ppt"), "PowerPoint (.pptx/.ppt)"),
        (r"\b(?:file\s+|tệp\s+|tep\s+)?(?:markdown|\.md)\b", (".md",), "Markdown (.md)"),
    ]
    matched_ext_labels: list[str] = []
    for ext_pat, ext_tuple, ext_label in ext_specs:
        if re.search(ext_pat, working, flags=re.IGNORECASE):
            for e in ext_tuple:
                if e not in extensions:
                    extensions.append(e)
            matched_ext_labels.append(ext_label)
            working = re.sub(ext_pat, " ", working, flags=re.IGNORECASE).strip()

    if slide_rule:
        # Slide rule restricts candidate extensions to presentations + PDFs with slide indicators
        if not extensions:
            extensions = list(SLIDE_ALLOWED_EXTENSIONS)
        chips.insert(0, "Loại: Slide (.pptx/.ppt/.key hoặc PDF slide/bài giảng)")
        scope_notes.append(
            "Quy tắc Slide: ưu tiên .pptx/.ppt/.key; chỉ nhận .pdf có tên hoặc tóm tắt chứa dấu hiệu slide/bài giảng."
        )
    elif report_rule:
        chips.insert(0, "Loại: Báo cáo")
        if matched_ext_labels:
            chips.append("Định dạng: " + ", ".join(matched_ext_labels))
    elif matched_ext_labels:
        resource_kind = "file"
        chips.insert(0, "Định dạng: " + ", ".join(matched_ext_labels))

    if sort == "modified_desc":
        chips.append("Sắp xếp: Mới sửa nhất (modified_at ↓)")
        scope_notes.append(
            "Sắp xếp theo thời gian sửa đổi mới nhất (modified_at DESC) trước khi giới hạn số lượng trên kho chỉ mục cục bộ."
        )

    # 6. Strip remaining leading/trailing search filler words ONLY when a structured rule was triggered
    has_structured = bool(
        slide_rule
        or report_rule
        or extensions
        or date_min is not None
        or sort != "relevance"
        or needs_clarification
    )
    if has_structured:
        filler_lead_tokens = (
            r"(?:"
            r"hãy|hay|giúp\s+tôi|giup\s+toi|cho\s+tôi|cho\s+toi|"
            r"tìm\s+kiếm|tim\s+kiem|tìm|tim|xem|lấy|lay|liệt\s+kê|liet\s+ke|hiển\s+thị|hien\s+thi|search|find|show|get|"
            r"các|cac|những|nhung|mọi|moi|tất\s+cả|tat\s+ca|bản|ban|cuốn|cuon|bộ|bo|"
            r"tài\s+liệu|tai\s+lieu|tệp\s+tin|tep\s+tin|tệp|tep|file|files|documents?|"
            r"về|ve|môn|mon|của|cua|cho|for|about|on"
            r")"
        )
        while True:
            m = re.match(r"^" + filler_lead_tokens + r"(?:\s+|$)", working, flags=re.IGNORECASE)
            if not m:
                break
            working = working[m.end():].strip()

        filler_tail_tokens = (
            r"(?:"
            r"đã\s+sửa|da\s+sua|sửa\s+đổi|sua\s+doi|chỉnh\s+sửa|chinh\s+sua|"
            r"cập\s+nhật|cap\s+nhat|sửa|sua|trong\s+kho|trong\s+máy|trong\s+may"
            r")"
        )
        while True:
            m = re.search(r"(?:^|\s+)" + filler_tail_tokens + r"$", working, flags=re.IGNORECASE)
            if not m:
                break
            working = working[:m.start()].strip()
        working = re.sub(r"\s+", " ", working).strip(" .,!?:;\"'")
        if working:
            chips.insert(0, f"Từ khóa: {working}")
    else:
        working = cleaned

    return FinderIntentPlan(
        raw_query=raw_query,
        action="search",
        query_terms=working,
        resource_kind=resource_kind,
        extensions=tuple(extensions),
        excluded_extensions=(),
        date_min=date_min,
        date_max=date_max,
        date_max_exclusive=date_max_exclusive,
        date_field=date_field,
        sort=sort,
        slide_rule=slide_rule,
        report_rule=report_rule,
        target_app_query="",
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
        conflicting_constraints=conflicting_constraints,
        interpretation_chips=tuple(chips),
        scope_note=" ".join(scope_notes).strip(),
    )
