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

    win = OmnibarWindow()
    win.show()
    win.set_expanded(True)
    win.switch_section(1)  # Section 1: Tệp tin
    app.processEvents()

    # Inject mock search results
    items = [
        SearchResultItem(
            file_path="/Users/thundercock2/Documents/BaiGiang_CSDL_Tuan4.pdf",
            file_name="BaiGiang_CSDL_Tuan4.pdf",
            file_ext=".pdf",
            file_size=2458900,
            modified_at=time.time() - 3600,
            score=95.0,
            explanation="Khớp chính xác từ khóa và ngữ nghĩa bài giảng CSDL",
            snippet="Chương 4: Mô hình dữ liệu quan hệ, đại số quan hệ và khóa chính...",
        ),
        SearchResultItem(
            file_path="/Users/thundercock2/Documents/DeCuong_MonHoc_Python.docx",
            file_name="DeCuong_MonHoc_Python.docx",
            file_ext=".docx",
            file_size=1048576,
            modified_at=time.time() - 86400 * 2,
            score=82.0,
            explanation="Khớp đề cương học phần lập trình Python",
            snippet="Mục tiêu môn học: Cung cấp kiến thức cơ bản và nâng cao về Python...",
        ),
        SearchResultItem(
            file_path="/Users/thundercock2/Documents/BangDiem_HocKy1.xlsx",
            file_name="BangDiem_HocKy1.xlsx",
            file_ext=".xlsx",
            file_size=524288,
            modified_at=time.time() - 86400 * 5,
            score=74.0,
            explanation="Bảng điểm học kỳ 1 năm học 2025-2026",
            snippet="Tổng kết: CPA 7.82, xếp loại Khá, tích lũy 64 tín chỉ...",
        ),
    ]

    for item in items:
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import Qt
        list_item = QListWidgetItem(win.result_list)
        list_item.setData(Qt.ItemDataRole.UserRole, item)
        win.result_list.addItem(list_item)

    win.result_list.setCurrentRow(0)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()

    win.grab().save("scratch/live_chuot_files.png")
    print("Saved live_chuot_files.png successfully!")
    win.close()
