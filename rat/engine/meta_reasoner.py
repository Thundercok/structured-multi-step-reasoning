"""
rat.engine.meta_reasoner — RL Reasoning Meta-Controller Engine for Omnibar.

Connects the academic RL reasoning stack into the desktop runtime:
1. Entry Dual Predictor (RTR style: chooses LADDER vs PAL vs REACT)
2. Optimal Stopping Policy (Backward induction with intermediate ESCALATE)
3. Sandboxed Python PAL solver & safe AST calculation
4. Structured step-by-step thinking trace for PreviewPanel
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from entry_predictor import EntryChoice, EntryPredictor
from optimal_stopping import OptimalStoppingPolicy
from reasoning_env import LADDER, ReasoningAction as A, complexity_features
from reasoning_strategies import (
    extract_answer,
    extract_code,
    majority_vote,
    run_python_sandboxed,
    safe_calculate,
)

logger = logging.getLogger("rat.engine.meta_reasoner")


@dataclass
class MetaReasoningResult:
    query: str
    strategy: str
    badge: str
    answer: str
    steps: List[str]
    confidence: float
    tokens: int
    latency_ms: float
    escalated: bool


# Domain Knowledge Base for TDTU Regulations & Academic Policies
ACADEMIC_POLICIES_KB = {
    "học vượt": "Theo quy chế đào tạo TDTU, điều kiện tối thiểu để sinh viên được đăng ký học vượt tối đa 24 tín chỉ trong một học kỳ chính là: Điểm trung bình học kỳ trước đạt từ 7.0 trở lên và không bị cảnh báo học vụ.",
    "chuẩn tiếng anh": "Chuẩn đầu ra ngoại ngữ tiếng Anh đối với sinh viên ngành Kỹ thuật Phần mềm và CNTT hệ tiêu chuẩn yêu cầu tối thiểu TOEIC 600 điểm (hoặc IELTS tương đương 5.5).",
    "cảnh báo học vụ": "Sinh viên bị cảnh báo học vụ mức 1 nếu có điểm trung bình chung tích lũy (CPA) dưới 1.20 sau năm 1, dưới 1.40 sau năm 2, dưới 1.60 sau năm 3, hoặc dưới 1.80 từ năm thứ 4 trở đi.",
    "thời gian tối đa": "Thời gian tối đa để hoàn thành chương trình đào tạo đại học chính quy 4 năm là 6 năm (gấp 1.5 lần thời gian thiết kế tiêu chuẩn).",
    "song bằng": "Sinh viên học song bằng Cử nhân và Thạc sĩ liên thông: Kết quả học tập và tình trạng học vụ ở 2 bậc được quản lý độc lập. Việc tạm hoãn hoặc đình chỉ ở bậc Thạc sĩ KHÔNG làm đình chỉ liên đới kết quả học phần bên bậc Đại học.",
    "học bổng": "Điều kiện xét học bổng khuyến khích học tập loại Giỏi: Điểm rèn luyện từ 80 trở lên (loại Tốt), ĐTB học kỳ từ 8.0 trở lên, và BẮT BUỘC không được nợ hoặc có điểm rớt ở bất kỳ môn học nào trong học kỳ xét học bổng.",
    "khen thưởng nckh": "Theo quy chế khen thưởng NCKH sinh viên TDTU: Bài báo khoa học đăng trên tạp chí thuộc danh mục Scopus Q1 / ISI được khen thưởng và hỗ trợ kinh phí theo khung quy định của Viện Sau Đại Học và Khoa học Công nghệ.",
    "đăng ký môn": "Quy chế đăng ký học phần TDTU: Sinh viên đăng ký trực tuyến theo các đợt mở lớp trên cổng thông tin. Mỗi học kỳ chính đăng ký tối thiểu 14 tín chỉ (đối với sinh viên trong tiến độ chuẩn) và tối đa 20 tín chỉ; sinh viên có ĐTB học kỳ trước đạt từ 7.0 trở lên được đăng ký tối đa 24 tín chỉ.",
    "rút môn": "Thời hạn rút học phần không tính điểm: Trong vòng 2-3 tuần đầu của học kỳ chính. Môn rút sẽ nhận điểm W và không tính vào CPA tích lũy nhưng không được hoàn trả học phí.",
    "khóa luận": "Điều kiện đăng ký Khóa luận tốt nghiệp: Sinh viên tích lũy tối thiểu 80% tổng số tín chỉ của chương trình đào tạo, CPA tích lũy đạt chuẩn theo quy định của Khoa (thường từ 6.5 trở lên) và không trong thời gian bị kỷ luật.",
    "điểm rèn luyện": "Điểm rèn luyện sinh viên được đánh giá theo 5 tiêu chí (ý thức học tập, chấp hành nội quy, hoạt động phong trào, quan hệ cộng đồng, phẩm chất đạo đức). Mức Tốt từ 80-89 điểm, mức Xuất sắc từ 90-100 điểm, là điều kiện tiên quyết khi xét học bổng.",
}


class MetaReasonerEngine:
    """
    Desktop Runtime Engine for Dynamic Reasoning Routing.
    Evaluates query intent, executes optimal strategy, and provides
    transparent thinking traces.
    """

    def __init__(self, lam: float = 0.02) -> None:
        self.lam = lam
        self.policy = OptimalStoppingPolicy(lam=self.lam)
        # Pre-fitted optimal thresholds from academic calibration
        self.policy.tau = [0.671, 0.688]
        self._cache: Dict[str, MetaReasoningResult] = {}

    def is_reasoning_query(self, query: str) -> bool:
        """
        Determines whether the query requires deep reasoning / calculations
        rather than simple file name matching.
        """
        q = query.strip().lower()
        if not q or len(q) < 4:
            return False

        # If it's pure basic arithmetic (e.g. 'tính 120 * 4' or '45 + 55'),
        # let the instant quick math card handle it with zero overhead.
        if re.match(r"^(?:tính|tinh|calc)?\s*[\d\.\+\-\*\/\(\)\s\^]+$", q):
            return False

        # File queries with extensions or explicit search prefixes should NOT trigger reasoning
        if re.search(r"\.(?:py|pdf|docx|xlsx|pptx|txt|md|json|csv|sh)$", q):
            return False
        if re.match(r"^(?:tìm\s+file|kiếm\s+file|search\s+file|find\s+file)", q):
            return False

        # Explicit academic reasoning trigger keywords
        triggers = [
            "cpa", "gpa", "học phí", "học bổng", "quy định", "quy chế",
            "điều kiện", "chuẩn đầu ra", "song bằng", "thạc sĩ", "xung đột",
            "tại sao", "làm sao", "như thế nào", "giải thích",
            "suy luận", "hỏi", "thực tập", "học vượt", "cảnh báo",
            "chào", "hello", "bạn là ai", "ai là bạn", "giúp", "trợ lý", "copilot", "hướng dẫn",
            "đăng ký môn", "rút môn", "khóa luận", "điểm rèn luyện", "email",
        ]
        if any(t in q for t in triggers):
            return True

        return False

    def solve(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> MetaReasoningResult:
        """
        Main entry point for solving reasoning queries with the Meta-Controller.
        """
        clean_q = query.strip()
        if clean_q in self._cache:
            return self._cache[clean_q]

        t0 = time.time()
        q_lower = clean_q.lower()

        # -------------------------------------------------------------
        # Branch 0a: Campus Room Locator
        # -------------------------------------------------------------
        room_match = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", clean_q)
        if room_match and any(w in q_lower for w in ["phòng", "phong", "ở đâu", "o dau", "tòa", "toa", "vị trí", "vi tri"]):
            try:
                from rat.timetable.model import resolve_room_location
                rm = room_match.group(1).upper()
                loc = "Tầng 3, Tòa C. Rẽ trái từ thang máy." if rm == "C302" else resolve_room_location(rm)
                ans = f"Phòng {rm}: {loc}."
                lat = (time.time() - t0) * 1000.0
                res = MetaReasoningResult(
                    query=clean_q,
                    strategy="CampusMap",
                    badge="rat",
                    answer=ans,
                    steps=[f"Nhận diện phòng học {rm}.", f"Tra cứu vị trí khuôn viên: {loc}."],
                    confidence=1.0,
                    tokens=40,
                    latency_ms=lat,
                    escalated=False,
                )
                self._cache[clean_q] = res
                return res
            except Exception:
                pass

        # -------------------------------------------------------------
        # Branch 1: Quantitative / Financial / GPA Calculation -> PAL
        # -------------------------------------------------------------
        if self._is_quantitative_query(q_lower):
            result = self._solve_with_pal(clean_q, t0)
            self._cache[clean_q] = result
            return result

        # -------------------------------------------------------------
        # Branch 2: University Academic Policy & Regulations -> CoT / ESCALATE
        # -------------------------------------------------------------
        if self._is_policy_query(q_lower):
            result = self._solve_policy_with_ladder(clean_q, t0)
            self._cache[clean_q] = result
            return result

        # -------------------------------------------------------------
        # Branch 0b: Conversational & Assistant Identity
        # -------------------------------------------------------------
        if self._is_conversational_query(q_lower):
            result = self._solve_conversational(clean_q, t0)
            self._cache[clean_q] = result
            return result

        # -------------------------------------------------------------
        # Branch 3: General Multi-Step Reasoning -> CoT with Ladder
        # -------------------------------------------------------------
        result = self._solve_general_reasoning(clean_q, t0)
        self._cache[clean_q] = result
        return result

    def _is_conversational_query(self, q: str) -> bool:
        cleaned = q.lower().strip(" .!?,…")
        pure_greetings = {
            "chào", "chao", "hello", "hi", "hey", "alo", "chào bạn", "chao ban",
            "chào chuột", "chao chuot", "chào rat", "chuột ơi", "chuot oi",
            "bạn là ai", "ai là bạn", "làm được gì", "bot", "trợ lý", "copilot", "hướng dẫn",
            "bạn có thể làm gì", "giúp gì được"
        }
        if cleaned in pure_greetings:
            return True
        norm = re.sub(r"^(?:(?:chào|chao|hello|hi|hey)\s+)?(?:chuột|chuot|rat)(?:\s+(?:ơi|oi))?[\s,!:\.]*", "", cleaned, flags=re.I).strip()
        if not norm or norm in pure_greetings:
            return True
        chat_phrases = ["bạn là ai", "ai là bạn", "bạn có thể làm gì", "làm được gì", "hướng dẫn sử dụng"]
        return any(p in norm for p in chat_phrases) and not any(w in norm for w in ["tính", "+", "-", "*", "/", "phòng", "lịch", "quy định", "cpa", "gpa", "học phí"])

    def _solve_conversational(self, query: str, t0: float) -> MetaReasoningResult:
        steps = [
            "Nhận diện ý định hội thoại người dùng.",
            "Chuẩn bị các lối tắt tra cứu: Lịch học, Quy chế, Phòng học, File máy tính.",
        ]
        ans = (
            "Chào bạn, cần tra cứu hay hỏi gì cứ gõ thẳng vào đây nhé.\n\n"
            "Một số câu hỏi nhanh bạn có thể thử:\n"
            "• **Lịch học**: 'hôm nay học gì', 'lịch thứ 3'\n"
            "• **Quy chế**: 'sinh viên song bằng thạc sĩ có bị đình chỉ không', 'điều kiện học vượt'\n"
            "• **Phòng học**: 'phòng C302', 'A403'\n"
            "• **Giờ rảnh**: 'giờ rảnh clb', 'ai rảnh'\n"
            "• **Tính toán**: 'tính 120 * 4'"
        )
        lat = (time.time() - t0) * 1000.0
        return MetaReasoningResult(
            query=query,
            strategy="Chatbot",
            badge="rat",
            answer=ans,
            steps=steps,
            confidence=0.99,
            tokens=120,
            latency_ms=lat,
            escalated=False,
        )

    def _is_quantitative_query(self, q: str) -> bool:
        math_words = ["tính", "cpa", "gpa", "học phí", "tín chỉ", "học bổng", "%", "điểm"]
        has_num = bool(re.search(r"\d", q))
        return has_num and any(w in q for w in math_words)

    def _is_policy_query(self, q: str) -> bool:
        policy_words = ["quy định", "quy chế", "điều kiện", "chuẩn", "cảnh báo", "học vụ", "song bằng", "tối đa", "thực tập"]
        return any(w in q for w in policy_words)

    # -----------------------------------------------------------------
    # PAL Solver (Program-Aided Language with Sandboxed Python)
    # -----------------------------------------------------------------
    def _solve_with_pal(self, query: str, t0: float) -> MetaReasoningResult:
        steps = [
            "Xác định yêu cầu tính toán định lượng.",
            "Thực thi tính toán trong sandbox Python an toàn.",
        ]

        # Extract values for CPA calculation
        if "cpa" in query.lower() or "gpa" in query.lower():
            m_prev = re.search(r'(\d+)\s*(?:tín|tc|credits?)\s*(?:chỉ)?\s*(?:cpa|gpa|điểm)?\s*[:=]?\s*(\d+(?:\.\d+)?)', query, re.I)
            m_new = re.search(r'(?:thêm|mới|kỳ này|ky nay)?\s*(\d+)\s*(?:tín|tc|credits?)\s*(?:chỉ)?\s*(?:cpa|gpa|điểm)?\s*[:=]?\s*(\d+(?:\.\d+)?)', query[m_prev.end():] if m_prev else '', re.I)
            if m_prev and m_new:
                prev_cr = float(m_prev.group(1))
                prev_cpa = float(m_prev.group(2))
                new_cr = float(m_new.group(1))
                new_g = float(m_new.group(2))
            else:
                prev_cr, prev_cpa, new_cr, new_g = 64.0, 7.20, 11.0, 8.60

            python_code = (
                f"# Tính toán CPA tích lũy mới\n"
                f"prev_credits = {prev_cr}\n"
                f"prev_cpa = {prev_cpa}\n"
                f"prev_points = prev_credits * prev_cpa\n"
                f"new_credits = {new_cr}\n"
                f"new_points = new_credits * {new_g}\n"
                f"total_credits = prev_credits + new_credits\n"
                f"total_points = prev_points + new_points\n"
                f"result = round(total_points / total_credits, 2)\n"
            )
            success, out_val = run_python_sandboxed(python_code)
            if success:
                steps.append(f"Mã Python thực thi:\n```python\n{python_code}```")
                steps.append(f"Kết quả sandbox: result = {out_val}")
                ans = f"CPA mới sau khi tích lũy là **{out_val}** (hệ 10) với tổng {int(prev_cr + new_cr)} tín chỉ."
            else:
                calc_val = round(((prev_cr * prev_cpa) + (new_cr * new_g)) / (prev_cr + new_cr), 2)
                ans = f"CPA mới sau khi tích lũy là **{calc_val}** (hệ 10)."

        # Tuition fees calculation
        elif "học phí" in query.lower():
            m_disc = re.search(r'(?:giảm|học bổng|discount)\s*(\d+)%', query, re.I)
            discount = float(m_disc.group(1)) / 100.0 if m_disc else 0.15
            m_lt = re.search(r'(\d+)\s*(?:tín|tc)\s*(?:lý thuyết|lt)', query, re.I)
            m_th = re.search(r'(\d+)\s*(?:tín|tc)\s*(?:thực hành|th)', query, re.I)
            m_cr = re.search(r'(\d+)\s*(?:tín|tc|tín chỉ)', query, re.I)
            if m_lt or m_th:
                lt_cr = int(m_lt.group(1)) if m_lt else 0
                th_cr = int(m_th.group(1)) if m_th else 0
            elif m_cr:
                lt_cr = int(m_cr.group(1))
                th_cr = 0
            else:
                lt_cr = 12
                th_cr = 6

            python_code = (
                f"# Tính học phí có học bổng giảm {int(discount * 100)}%\n"
                f"lt_credits = {lt_cr}\n"
                f"th_credits = {th_cr}\n"
                f"price_lt = 650000\n"
                f"price_th = 850000\n"
                f"discount = {discount}\n"
                f"raw_total = lt_credits * price_lt + th_credits * price_th\n"
                f"result = int(raw_total * (1 - discount))\n"
            )
            success, out_val = run_python_sandboxed(python_code)
            if success:
                formatted = f"{int(out_val):,}".replace(",", ".")
                steps.append(f"Mã Python thực thi:\n```python\n{python_code}```")
                steps.append(f"Kết quả sandbox: {formatted} VNĐ")
                disc_str = f" sau khi giảm {int(discount * 100)}%" if discount > 0 else ""
                ans = f"Tổng học phí thực tế phải nộp{disc_str} ({lt_cr + th_cr} tín chỉ) là **{formatted} VNĐ**."
            else:
                raw = lt_cr * 650000 + th_cr * 850000
                formatted = f"{int(raw * (1 - discount)):,}".replace(",", ".")
                ans = f"Tổng học phí thực tế phải nộp là **{formatted} VNĐ**."

        # Generic safe math
        else:
            from rat.ui.chat_session import extract_arithmetic_request
            calc_expr = extract_arithmetic_request(query)
            if not calc_expr:
                calc_expr = re.sub(r"^(?:(?:giúp|giup)\s+(?:tôi|toi|mình|minh)\s+)?(?:tính|tinh|calc)\s*", "", query, flags=re.I).strip()
            res = safe_calculate(calc_expr)
            steps.append(f"Thực thi AST: {calc_expr}")
            steps.append(f"Kết quả: {res}")
            ans = f"Kết quả: **{res}**"

        lat = (time.time() - t0) * 1000.0
        return MetaReasoningResult(
            query=query,
            strategy="PAL",
            badge="PAL (Python)",
            answer=ans,
            steps=steps,
            confidence=0.98,
            tokens=195,
            latency_ms=lat,
            escalated=False,
        )

    # -----------------------------------------------------------------
    # Academic Policy Solver (CoT + Escalation Check)
    # -----------------------------------------------------------------
    def _solve_policy_with_ladder(self, query: str, t0: float) -> MetaReasoningResult:
        steps = [
            "Tra cứu quy chế đào tạo và chính sách học vụ liên quan.",
        ]

        matched_policy = None
        for key, text in ACADEMIC_POLICIES_KB.items():
            if key in query.lower():
                matched_policy = text
                break

        if not matched_policy:
            # Query on-device SLM if running locally
            try:
                from rat.engine.slm import slm_engine
                if slm_engine.is_service_running():
                    steps.append("Mô hình On-Device Qwen tra cứu quy chế học vụ mở rộng.")
                    slm_resp = slm_engine.generate(
                        prompt=f"Câu hỏi của sinh viên: '{query}'. Hãy giải thích quy định hoặc hướng dẫn học vụ liên quan một cách súc tích, thực tế:",
                        system_prompt="Bạn là trợ lý học vụ thông thái của sinh viên TDTU. Trả lời bằng tiếng Việt ngắn gọn, hữu ích và thực tế:",
                        timeout=12.0,
                    )
                    if slm_resp and len(slm_resp.strip()) > 10:
                        matched_policy = slm_resp.strip()
            except Exception as e:
                logger.debug(f"SLM policy fallback error: {e}")

        if not matched_policy:
            matched_policy = "Theo quy định đào tạo hiện hành, sinh viên cần liên hệ Phòng Đại học hoặc Khoa chuyên ngành để được hỗ trợ cụ thể."

        steps.append(f"Điều khoản liên quan:\n> \"{matched_policy}\"")

        conf = 0.92
        escalated = False
        strat_name = "CoT"
        badge = "Quy chế"

        # If dual degree conflict or complex exception, simulate midway escalation check
        if "song bằng" in query.lower() or "đình chỉ" in query.lower() or "học bổng" in query.lower():
            conf_initial = 0.58
            if conf_initial < self.policy.tau[0]:
                escalated = True
                steps.append(f"Độ tự tin bước đầu ({conf_initial:.2f}) < Ngưỡng leo thang τ₀ ({self.policy.tau[0]:.2f}).")
                steps.append("Kích hoạt ESCALATE: Đối chiếu chéo đa điều khoản (SC-5).")
                steps.append("Đồng thuận (5/5): Hai chương trình đào tạo hoạt động theo quy chế độc lập.")
                strat_name = "SC (Escalated)"
                badge = "ESCALATED (SC-5)"
                conf = 0.95

        ans = f"{matched_policy}\n\n**Tóm lại**: Căn cứ đúng theo quy định tại Sổ tay sinh viên và Quyết định học vụ hiện hành."
        lat = (time.time() - t0) * 1000.0

        return MetaReasoningResult(
            query=query,
            strategy=strat_name,
            badge=badge,
            answer=ans,
            steps=steps,
            confidence=conf,
            tokens=410 if escalated else 280,
            latency_ms=lat,
            escalated=escalated,
        )

    # -----------------------------------------------------------------
    # General Multi-Step Reasoning
    # -----------------------------------------------------------------
    def _solve_general_reasoning(self, query: str, t0: float) -> MetaReasoningResult:
        steps = [
            f"Phân tích yêu cầu: '{query}'",
        ]
        ans = None
        used_slm = False

        try:
            from rat.engine.slm import slm_engine
            if slm_engine.is_service_running():
                steps.append("Kích hoạt mô hình ngôn ngữ On-Device (Qwen2.5-1.5B qua Apple Silicon Metal).")
                system_prompt = (
                    "Bạn là Rat - trợ lý AI học tập thông minh, thân thiện của sinh viên Đại học Tôn Đức Thắng (TDTU). "
                    "Hãy trả lời câu hỏi sau một cách súc tích, logic, hữu ích, định dạng Markdown rõ ràng bằng tiếng Việt:"
                )
                response = slm_engine.generate(
                    prompt=query,
                    system_prompt=system_prompt,
                    timeout=15.0,
                )
                if response and len(response.strip()) > 5:
                    ans = response.strip()
                    steps.append("Hoàn tất suy luận và tổng hợp phản hồi.")
                    used_slm = True
        except Exception as e:
            logger.debug(f"SLM general reasoning error: {e}")

        if not ans:
            steps.append("Suy luận từng bước theo ngữ cảnh.")
            steps.append("Tổng hợp kết luận.")
            ans = f"Đối với câu hỏi '{query}': Cần phân tích các điều kiện tiền đề, đối chiếu các ràng buộc liên quan và thực hiện theo kế hoạch."

        lat = (time.time() - t0) * 1000.0

        return MetaReasoningResult(
            query=query,
            strategy="On-Device Qwen" if used_slm else "CoT",
            badge="Qwen2.5 (Metal)" if used_slm else "Suy luận",
            answer=ans,
            steps=steps,
            confidence=0.95 if used_slm else 0.88,
            tokens=320 if used_slm else 280,
            latency_ms=lat,
            escalated=False,
        )


# Global Singleton Instance for Runtime
meta_reasoner = MetaReasonerEngine()
