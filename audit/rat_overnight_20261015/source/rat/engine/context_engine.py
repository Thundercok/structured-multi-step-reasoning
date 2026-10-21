"""
rat.engine.context_engine — Deep Context Engineering & Semantic Intent Deconstructor.
Transforms messy, non-technical human queries into rich conceptual representations.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from rat.engine.context_parser import ContextParser, ParsedContext, remove_accents
from rat.engine.slm import slm_engine

logger = logging.getLogger("rat.context_engine")

# Rich Semantic Concept Knowledge Base for Vietnamese non-tech users
CONCEPT_ONTOLOGY: Dict[str, Dict[str, Any]] = {
    "dsa_academic": {
        "triggers": [
            "cau truc du lieu", "giai thuat", "dsa", "mon dsa", "bai tap dsa", "lab dsa",
            "thay dung", "thuc hanh dsa", "cay nhi phan", "do thi", "ngan xep", "hang doi"
        ],
        "synonyms": ["dsa", "data structures", "algorithms", "lab", "assignment", "bài tập", "cấu trúc dữ liệu", "giải thuật", "thầy dũng"],
        "extensions": [".pdf", ".docx", ".py", ".cpp", ".java", ".zip"],
        "intent_desc": "Bài tập/Tài liệu môn Cấu trúc dữ liệu và Giải thuật (DSA)",
    },
    "finance_expenses": {
        "triggers": [
            "tien com", "an trua", "chi phi", "an uong", "tien phong", "tien nha",
            "bang luong", "hoa don", "thanh toan", "tam ung", "quyet toan", "ngan sach"
        ],
        "synonyms": ["tiền cơm", "chi phí", "ăn trưa", "hóa đơn", "thanh toán", "ngân sách", "bảng tính", "quyết toán", "lương"],
        "extensions": [".xlsx", ".xls", ".csv", ".pdf", ".docx"],
        "intent_desc": "Bảng tính chi phí, tiền cơm, tiền phòng hoặc thanh toán hóa đơn",
    },
    "thesis_research": {
        "triggers": [
            "do an", "khoa luan", "tot nghiep", "de tai", "capstone", "thesis",
            "bao cao tot nghiep", "slide bao ve", "thuyet trinh do an", "nghien cuu"
        ],
        "synonyms": ["đồ án", "khóa luận", "tốt nghiệp", "capstone", "thesis", "báo cáo", "slide", "thuyết trình", "nghiên cứu", "kỷ yếu"],
        "extensions": [".pdf", ".docx", ".pptx", ".ppt"],
        "intent_desc": "Đồ án tốt nghiệp, khóa luận hoặc tài liệu nghiên cứu học thuật",
    },
    "autonomous_ai": {
        "triggers": [
            "xe tu hanh", "giao thong", "dieu huong", "un tac", "camera giao thong",
            "vrp", "routing", "vehicle", "alns", "ddqn", "reinforcement learning"
        ],
        "synonyms": ["xe tự hành", "giao thông", "điều hướng", "ùn tắc", "camera", "vrp", "vehicle routing", "alns", "rl", "học tăng cường"],
        "extensions": [".pdf", ".docx", ".py"],
        "intent_desc": "Tài liệu/Nghiên cứu về xe tự hành, điều hướng giao thông và thuật toán AI/VRP",
    },
    "meeting_work": {
        "triggers": [
            "hop", "cuoc hop", "bien ban", "tong ket", "ke hoach", "tuan nay", "thang nay",
            "sep", "bien ban hop", "noi dung hop", "bien ban lam viec",
            "hoi nghi", "hoi thao", "meeting"
        ],
        "synonyms": ["biên bản họp", "biên bản", "cuộc họp", "kế hoạch", "tổng kết", "tiến độ", "hội nghị", "hội thảo", "meeting", "minutes", "task", "roadmap"],
        "extensions": [".docx", ".doc", ".pdf", ".txt", ".md"],
        "intent_desc": "Biên bản họp, hội nghị, kế hoạch làm việc hoặc tài liệu tổng kết",
    },
    "lifestyle_health": {
        "triggers": [
            "loi song", "suc khoe", "dan ong", "nam gioi", "the thao", "tap luyen",
            "phong cach", "dinh duong", "nang dong"
        ],
        "synonyms": ["lối sống", "sức khỏe", "đàn ông", "nam giới", "năng động", "phong cách", "lifestyle", "thể thao", "rèn luyện"],
        "extensions": [".docx", ".pdf", ".doc"],
        "intent_desc": "Bài viết/Tài liệu về lối sống, sức khỏe và phong cách sống",
    },
    "crawler_scraping": {
        "triggers": [
            "cao du lieu", "crawler", "spider", "crawl", "scrape", "boc tach",
            "lay du lieu", "web scraper", "tu dong hoa web"
        ],
        "synonyms": ["cào dữ liệu", "crawler", "spider", "thu thập dữ liệu", "web scraping", "bóc tách web", "tự động hóa"],
        "extensions": [".py", ".pdf", ".docx", ".json"],
        "intent_desc": "Mã nguồn hoặc tài liệu về công cụ cào dữ liệu web (Spider/Crawler)",
    },
    "visual_nature_landscapes": {
        "triggers": [
            "hoang hon", "binh minh", "bien", "bai bien", "nui", "doi nui", "phong canh",
            "thien nhien", "bau troi", "may", "rung", "cay coi", "hoa", "vuon hoa", "chieu ta"
        ],
        "synonyms": ["hoàng hôn", "bình minh", "biển", "bãi biển", "phong cảnh", "thiên nhiên", "bầu trời", "núi", "rừng", "sunset", "beach", "nature", "landscape", "sky"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "intent_desc": "Hình ảnh phong cảnh thiên nhiên, hoàng hôn, bãi biển hoặc cây cối",
    },
    "visual_pets_animals": {
        "triggers": [
            "cho", "cun", "meo", "thu cung", "vat nuoi", "dong vat", "chim", "ca", "pet", "dog", "cat"
        ],
        "synonyms": ["chó", "cún", "mèo", "thú cưng", "vật nuôi", "động vật", "dog", "puppy", "cat", "kitten", "pet", "animal"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "intent_desc": "Hình ảnh thú cưng, chó, mèo hoặc động vật",
    },
    "visual_food_dining": {
        "triggers": [
            "do an", "mon an", "am thuc", "an uong", "ca phe", "cafe", "tra", "pizza",
            "banh ngot", "trai cay", "bua an", "quan an", "nha hang"
        ],
        "synonyms": ["đồ ăn", "món ăn", "ẩm thực", "cà phê", "cafe", "pizza", "bánh ngọt", "trái cây", "food", "dining", "dish", "coffee"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "intent_desc": "Hình ảnh đồ ăn, món ăn, đồ uống hoặc ẩm thực",
    },
    "visual_receipt_id": {
        "triggers": [
            "anh hoa don", "anh chuyen khoan", "anh sao ke", "can cuoc", "cccd", "cmnd",
            "bang lai xe", "ho chieu", "ma qr", "qr chuyen tien", "bill chuyen khoan"
        ],
        "synonyms": ["hóa đơn", "biên lai", "chuyển khoản", "sao kê", "căn cước", "cccd", "bằng lái xe", "hộ chiếu", "mã qr", "receipt", "bill", "payment", "id card"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp", ".pdf"],
        "intent_desc": "Hình ảnh hóa đơn, biên lai thanh toán, mã QR hoặc giấy tờ tùy thân",
    },
    "visual_charts_diagrams": {
        "triggers": [
            "bieu do", "do thi", "so do", "thong ke", "chart", "diagram", "graph", "infographic"
        ],
        "synonyms": ["biểu đồ", "đồ thị", "sơ đồ", "bảng biểu", "thống kê", "chart", "diagram", "graph", "plot"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp", ".pptx", ".pdf"],
        "intent_desc": "Hình ảnh hoặc slide chứa biểu đồ, đồ thị và sơ đồ thống kê",
    },
    "visual_screenshots": {
        "triggers": [
            "anh chup man hinh", "screenshot", "cap man hinh", "anh giao dien", "screen capture"
        ],
        "synonyms": ["ảnh chụp màn hình", "screenshot", "chụp màn hình", "giao diện", "màn hình", "screen capture", "display"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "intent_desc": "Ảnh chụp màn hình (screenshot) hoặc giao diện phần mềm",
    },
    "visual_vehicles": {
        "triggers": [
            "xe hoi", "o to", "xe may", "xe dap", "may bay", "car", "motorcycle", "vehicle"
        ],
        "synonyms": ["xe hơi", "ô tô", "xe máy", "xe đạp", "máy bay", "xe cộ", "car", "vehicle", "automobile", "motorcycle"],
        "extensions": [".png", ".jpg", ".jpeg", ".webp"],
        "intent_desc": "Hình ảnh phương tiện giao thông, xe hơi, ô tô hoặc xe máy",
    },
    "provenance_sources": {
        "triggers": [
            "tai tu", "tai ve tu", "link web", "google docs", "google drive", "google slides",
            "overleaf", "telegram", "zalo", "safari", "chrome", "github", "slack", "messenger",
            "nguon web", "trang web"
        ],
        "synonyms": ["google docs", "google drive", "google slides", "overleaf", "telegram", "zalo", "safari", "chrome", "github", "slack", "web", "download"],
        "extensions": [],
        "intent_desc": "Tệp tin được tải về từ nguồn web hoặc ứng dụng cụ thể (Google Docs, Overleaf, Telegram, Safari, Chrome...)",
    },
    "exam_test": {
        "triggers": [
            "de thi", "kiem tra", "on thi", "on tap", "trac nghiem", "dap an",
            "de cuong", "midterm", "final", "exam", "quiz", "test"
        ],
        "synonyms": ["đề thi", "kiểm tra", "ôn thi", "trắc nghiệm", "đáp án", "đề cương", "exam", "test", "midterm", "final"],
        "extensions": [".pdf", ".docx", ".doc", ".pptx", ".xlsx"],
        "intent_desc": "Đề thi, bài kiểm tra, đề cương ôn tập hoặc đáp án",
    },
    "homework_assignment": {
        "triggers": [
            "bai tap", "bai tap lon", "btl", "assignment", "homework", "lab",
            "thuc hanh", "bai lam", "nop bai", "han nop"
        ],
        "synonyms": ["bài tập", "bài tập lớn", "BTL", "assignment", "homework", "thực hành", "lab", "nộp bài", "hạn nộp"],
        "extensions": [".pdf", ".docx", ".py", ".cpp", ".java", ".zip", ".xlsx"],
        "intent_desc": "Bài tập, bài tập lớn, thực hành hoặc assignment môn học",
    },
    "lecture_material": {
        "triggers": [
            "bai giang", "giao trinh", "tai lieu hoc", "chuong",
            "lecture", "textbook", "reading", "syllabus", "de cuong mon hoc"
        ],
        "synonyms": ["bài giảng", "giáo trình", "tài liệu", "chương", "lecture", "textbook", "syllabus", "đề cương môn học"],
        "extensions": [".pdf", ".docx", ".pptx", ".ppt"],
        "intent_desc": "Bài giảng, giáo trình hoặc tài liệu học tập",
    },
}


class EnrichedContext:
    """Rich semantic representation of a search query."""

    def __init__(
        self,
        raw_query: str,
        base_context: ParsedContext,
        matched_concepts: List[str],
        expanded_keywords: List[str],
        recommended_extensions: List[str],
        semantic_query_text: str,
        ai_intent_summary: str,
    ) -> None:
        self.raw_query = raw_query
        self.base_context = base_context
        self.matched_concepts = matched_concepts
        self.expanded_keywords = expanded_keywords
        self.recommended_extensions = recommended_extensions
        self.semantic_query_text = semantic_query_text
        self.ai_intent_summary = ai_intent_summary


class ContextEngine:
    """Engine responsible for deep context understanding and intent expansion."""

    @classmethod
    def enrich_query(cls, raw_query: str) -> EnrichedContext:
        """
        Enrich messy natural language into a comprehensive conceptual search representation.
        Runs in < 2ms using the Vietnamese Semantic Concept Knowledge Base.
        """
        cleaned = raw_query.strip()
        base_ctx = ContextParser.parse_query(cleaned)
        q_norm = remove_accents(cleaned).lower()

        matched_concepts: List[str] = []
        expanded_keywords: Set[str] = set(base_ctx.keywords)
        recommended_exts: Set[str] = set(base_ctx.extensions)
        intent_summaries: List[str] = []

        # Check concept triggers with exact word boundary matching
        for concept_id, concept_data in CONCEPT_ONTOLOGY.items():
            triggers = concept_data["triggers"]
            is_matched = False
            for trig in triggers:
                if re.search(r"\b" + re.escape(trig) + r"\b", q_norm):
                    is_matched = True
                    break

            if is_matched:
                matched_concepts.append(concept_id)
                intent_summaries.append(concept_data["intent_desc"])
                for syn in concept_data["synonyms"]:
                    expanded_keywords.add(syn)
                for ext in concept_data["extensions"]:
                    recommended_exts.add(ext)

        # Build semantic search text for Vector Embedder
        expanded_kw_list = list(expanded_keywords)
        if intent_summaries:
            ai_intent_summary = " • ".join(intent_summaries)
            semantic_query_text = f"{cleaned}. {' '.join(expanded_kw_list[:8])}. {ai_intent_summary}"
        else:
            ai_intent_summary = f"Tìm kiếm tệp liên quan đến: {', '.join(base_ctx.keywords) if base_ctx.keywords else cleaned}"
            semantic_query_text = f"{cleaned} {' '.join(expanded_kw_list)}"

        return EnrichedContext(
            raw_query=raw_query,
            base_context=base_ctx,
            matched_concepts=matched_concepts,
            expanded_keywords=expanded_kw_list,
            recommended_extensions=list(recommended_exts),
            semantic_query_text=semantic_query_text,
            ai_intent_summary=ai_intent_summary,
        )


context_engine = ContextEngine()
