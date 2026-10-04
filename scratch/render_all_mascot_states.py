import sys
import os
import time
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

with patch("rat.ui.omnibar.Database") as mock_db, patch("rat.ui.omnibar.SearchEngine") as mock_eng:
    mock_db_inst = MagicMock()
    mock_db_inst.get_stats.return_value = {"total_files": 88}
    mock_db_inst.get_recent_documents.return_value = []
    mock_db.return_value = mock_db_inst

    mock_eng_inst = MagicMock()
    mock_eng_inst.search.return_value = {"results": [], "latency_ms": 5, "reasoning_trace": None, "plan": None}
    mock_eng.return_value = mock_eng_inst

    from rat.ui.omnibar import OmnibarWindow
    from rat.engine.reranker import SearchResultItem

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Expanded Single Unified Chatbox
    win = OmnibarWindow()
    win.show()
    win.set_expanded(True)
    app.processEvents()

    win.chat_stream.add_user_message("Thứ 4 tuần này tui có môn gì không Chuột?")
    
    mock_file = SearchResultItem(
        file_path="/Users/thundercock2/Documents/BaiGiang_CSDL_Tuan4.pdf",
        file_name="BaiGiang_CSDL_Tuan4.pdf",
        file_ext=".pdf",
        file_size=2458900,
        modified_at=time.time() - 86400,
        score=92.0,
        explanation="Slide bài giảng CSDL tuần 4",
        snippet="Chương 4: Mô hình dữ liệu quan hệ và đại số quan hệ...",
    )

    win.chat_stream.add_assistant_message(
        answer="Chuột đã kiểm tra TKB Thứ Tư cho bạn nè:\n\n• **Tiết 1–3** (06:45 – 09:15): **Lập trình Python** (Phòng C302)\n• **Tiết 7–9** (12:30 – 15:00): **Cơ sở dữ liệu** (Phòng B204)\n\nNhớ đi sớm xíu kẻo kẹt thang máy nhà C nhé! Chuột tìm thấy slide môn CSDL tuần này bên dưới nè 🧀",
        reasoning_steps=[
            "Nhận diện truy vấn: Lịch học sinh viên ngày Thứ Tư (Day 3)",
            "Truy vấn ma trận TDTU_PERIODS: Khớp 2 ca học (Sáng C302, Chiều B204)",
            "Quét Semantic VectorCache: Khớp tài liệu bài giảng CSDL tuần 4 (Score: 92%)",
        ],
        latency_ms=12.4,
        strategy="Meta-RL",
        confidence=0.98,
        inline_files=[mock_file],
    )

    for _ in range(10):
        app.processEvents()
        time.sleep(0.02)

    win.grab().save("scratch/live_chuot_stream.png")
    print("Saved scratch/live_chuot_stream.png")

    # 2. Avatar button states
    win.set_mascot_state("searching")
    app.processEvents()
    time.sleep(0.02)
    win.companion_avatar_btn.grab().save("scratch/live_avatar_searching.png")

    win.set_mascot_state("thinking")
    app.processEvents()
    time.sleep(0.02)
    win.companion_avatar_btn.grab().save("scratch/live_avatar_thinking.png")

    win.set_mascot_state("angry")
    app.processEvents()
    time.sleep(0.02)
    win.companion_avatar_btn.grab().save("scratch/live_avatar_angry.png")

    # 3. Compact mode with peeking mascot
    win.set_expanded(False)
    win.set_mascot_state("idle")
    for _ in range(10):
        app.processEvents()
        time.sleep(0.02)
    win.grab().save("scratch/live_chuot_compact.png")
    print("Saved scratch/live_chuot_compact.png")

    win.close()
    print("All live screenshots rendered successfully!")
