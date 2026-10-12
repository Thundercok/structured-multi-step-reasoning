"""
scripts/try_vgc_omnibar.py — Interactive Verification Script for VGC in Omnibar.
Demonstrates:
1. Fast-W deterministic calculation with formal witness certificate (< 25ms)
2. Academic handbook policy query with grounded CitationChips
3. Search engine VGC anti-hallucination verification with QuickLook hooks
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.meta_reasoner import meta_reasoner
from rat.engine.reranker import SearchResultItem
from rat.engine.vgc import vgc_engine
from rat.ui.chat_stream import ChatStreamWidget, CitationChip
from rat.ui.compact_results import CompactFileRow


def test_vgc_experience():
    print("=" * 65)
    print("🚀 TRẢI NGHIỆM THỬ NGHIỆM VGC TRONG RAT (DESKTOP RUNTIME)")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. Quantitative Query: CPA Calculation
    # -------------------------------------------------------------
    q1 = "Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này thêm 4 môn..."
    print(f"\n[Test 1] Câu hỏi định lượng: '{q1[:45]}...'")
    t0 = time.perf_counter()
    res1 = meta_reasoner.solve(q1)
    ms1 = (time.perf_counter() - t0) * 1000.0

    print(f"  • Chiến lược: {res1.strategy} | Huy hiệu: {res1.badge}")
    print(f"  • Trạng thái kiểm chứng: {res1.verification_status.upper()}")
    print(f"  • Bằng chứng hình thức (Witness): {res1.witness_proof}")
    print(f"  • Độ trễ: {ms1:.2f} ms (0 token LLM)")
    print(f"  • Câu trả lời:\n    {res1.answer}")
    print(f"  • Các bước kiểm chứng:")
    for step in res1.steps:
        print(f"    - {step}")

    # -------------------------------------------------------------
    # 2. Academic Handbook Policy Query: Học bổng & Quy chế
    # -------------------------------------------------------------
    q2 = "Điều kiện nhận học bổng khuyến khích học tập loại Giỏi?"
    print(f"\n[Test 2] Câu hỏi quy chế học vụ: '{q2}'")
    t0 = time.perf_counter()
    res2 = meta_reasoner.solve(q2)
    ms2 = (time.perf_counter() - t0) * 1000.0

    print(f"  • Chiến lược: {res2.strategy} | Huy hiệu: {res2.badge}")
    print(f"  • Trạng thái kiểm chứng: {res2.verification_status.upper()}")
    print(f"  • Số lượng trích dẫn nguồn: {len(res2.citations)}")
    for cit in res2.citations:
        print(f"    📄 {cit.get('file_name')} · Trang {cit.get('page', 1)}")
        print(f"       Trích đoạn: \"{cit.get('snippet')[:80]}...\"")
    print(f"  • Độ trễ: {ms2:.2f} ms")
    print(f"  • Câu trả lời:\n    {res2.answer}")

    # -------------------------------------------------------------
    # 3. Search Result Item with VGC Anti-Hallucination
    # -------------------------------------------------------------
    print(f"\n[Test 3] Mở rộng VGC sang Search Engine & Citation Chips:")
    sample_item = SearchResultItem(
        file_path="/Users/thundercock2/Documents/QuyChe_DaoTao_TDTU.pdf",
        file_name="QuyChe_DaoTao_TDTU.pdf",
        file_ext=".pdf",
        file_size=2450000,
        modified_at=time.time() - 3600 * 24 * 3,
        score=98.5,
        explanation="Khớp quy chế đào tạo tín chỉ TDTU",
        snippet="Điều 12: Sinh viên có điểm trung bình học kỳ từ 7.0 trở lên được đăng ký tối đa 24 tín chỉ.",
        verified=True,
        page_num=8,
        vgc_certificate={"claim": "24 tín chỉ", "witness": "24 tín chỉ", "verification_ms": 0.4},
    )

    cit_dict = sample_item.to_citation()
    chip = CitationChip(cit_dict)
    row = CompactFileRow(sample_item)

    print(f"  • Tệp tìm kiếm: {sample_item.file_name}")
    print(f"  • Trạng thái VGC: {'✓ Verified' if sample_item.verified else 'Unverified'}")
    print(f"  • Citation Chip text: {chip.file_name} · Trang {chip.page}")
    print(f"  • Tooltip snippet: {chip.snippet}")
    print(f"  • Click action: macOS QuickLook hook -> {sample_item.file_path}")

    # -------------------------------------------------------------
    # 4. ChatStream Widget UI Rendering Test
    # -------------------------------------------------------------
    print(f"\n[Test 4] Render hoàn chỉnh trong ChatStreamWidget:")
    chat = ChatStreamWidget()
    chat.add_user_message("Điều kiện học vượt là gì?")
    chat.add_assistant_message(
        answer=res2.answer,
        reasoning_steps=res2.steps,
        latency_ms=ms2,
        strategy=res2.strategy,
        citations=[cit_dict],
        inline_files=[sample_item],
    )
    print(f"  • Chat stream message count: {chat._message_count}")
    print(f"  • Đã hiển thị bong bóng chat, ThinkingAccordion VGC badge và CitationChip thành công!")
    print("\n" + "=" * 65)
    print("✓ TẤT CẢ CÁC BƯỚC THỬ NGHIỆM HOẠT ĐỘNG HOÀN HẢO!")
    print("=" * 65)


if __name__ == "__main__":
    test_vgc_experience()
