"""
rat.engine.hyde — Hypothetical Document Embeddings (HyDE) & Multi-Query Generation.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

import numpy as np

from rat.config import config
from rat.engine.embedder import embedder
from rat.engine.slm import slm_engine

logger = logging.getLogger("rat.hyde")

HYDE_SYSTEM_PROMPT = """Bạn là trợ lý Context Engineering chuyên tạo văn bản giả lập (Hypothetical Document).
Nhiệm vụ: Dựa vào câu mô tả tìm file ngắn gọn hoặc mơ hồ của người dùng, hãy viết một đoạn văn bản ngắn (khoảng 3-4 câu) mô phỏng chính xác nội dung thực tế mà tệp tin đó sẽ chứa trên máy tính.
- Nếu là hợp đồng: Viết các điều khoản, bên A, bên B, số tiền, thời hạn.
- Nếu là báo cáo tài chính/kế toán: Viết các chỉ số doanh thu, chi phí, bảng kê, lợi nhuận.
- Nếu là bài tập/giáo trình: Viết các câu hỏi bài tập, lý thuyết, giải thuật.
- Nếu là mã nguồn code: Viết một đoạn code mẫu hoặc chú thích docstring.

Chỉ viết nội dung giả lập bằng tiếng Việt/tiếng Anh tự nhiên, không giải thích ngoài lề.
"""

MULTI_QUERY_PROMPT = """Dựa trên câu truy vấn tìm kiếm file sau, hãy sinh ra 3 cách diễn đạt tìm kiếm khác nhau (mỗi dòng 1 câu ngắn) tập trung vào:
1. Tiêu đề file khả dĩ
2. Đoạn văn nội dung chứa từ khóa quan trọng
3. Thuật ngữ chuyên môn / từ đồng nghĩa

Chỉ trả về 3 dòng, không đánh số:
"""


class HyDEEngine:
    """Hypothetical Document Embeddings & Multi-Query Generator."""

    def __init__(self) -> None:
        self.slm = slm_engine
        self.embedder = embedder

    def generate_hypothetical_document(self, query: str) -> Optional[str]:
        """Generate a realistic hypothetical document passage for query."""
        if not config.use_slm or not self.slm.is_model_installed():
            return None

        prompt = f"Tạo đoạn văn bản giả lập cho câu tìm kiếm:\n\"{query}\""
        try:
            hypo_text = self.slm.generate(
                prompt=prompt,
                system_prompt=HYDE_SYSTEM_PROMPT,
                json_format=False,
                timeout=5.0,
            )
            if hypo_text and len(hypo_text.strip()) > 20:
                return hypo_text.strip()
        except Exception as e:
            logger.debug(f"HyDE generation skipped: {e}")
        return None

    def generate_multi_queries(self, query: str) -> List[str]:
        """Generate 2-3 diverse search query formulations."""
        queries = [query]
        if not config.use_slm or not self.slm.is_model_installed():
            return queries

        prompt = f"{MULTI_QUERY_PROMPT}\n\"{query}\""
        try:
            res = self.slm.generate(
                prompt=prompt,
                json_format=False,
                timeout=4.0,
            )
            if res:
                lines = [
                    re.sub(r"^[\d\.\-\*\s]+", "", line).strip()
                    for line in res.splitlines()
                    if line.strip() and len(line.strip()) > 3
                ]
                for l in lines[:3]:
                    if l and l not in queries:
                        queries.append(l)
        except Exception as e:
            logger.debug(f"Multi-query generation skipped: {e}")

        return queries

    def get_hyde_query_vector(self, query: str) -> Tuple[np.ndarray, Optional[str], List[str]]:
        """
        Produce a blended Dense Query Vector combining raw query + HyDE hypothetical document.
        Returns: (blended_vector, hypothetical_text, multi_queries)
        """
        multi_queries = self.generate_multi_queries(query)
        hypo_text = self.generate_hypothetical_document(query)

        raw_vec = self.embedder.embed_query(query)

        if hypo_text:
            hypo_vec = self.embedder.embed_query(hypo_text)
            # Blend: 60% HyDE context + 40% raw query
            blended = 0.6 * hypo_vec + 0.4 * raw_vec
            norm = np.linalg.norm(blended)
            if norm > 1e-12:
                blended = blended / norm
            return blended.astype(np.float32), hypo_text, multi_queries

        return raw_vec, None, multi_queries


# Global HyDE instance
hyde_engine = HyDEEngine()
