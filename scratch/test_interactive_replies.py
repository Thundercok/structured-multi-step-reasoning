import sys
import os
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

with patch("rat.ui.omnibar.Database") as mock_db, patch("rat.ui.omnibar.SearchEngine") as mock_eng:
    mock_db_inst = MagicMock()
    mock_db_inst.get_stats.return_value = {"total_files": 88}
    mock_db_inst.get_recent_documents.return_value = []
    mock_db.return_value = mock_db_inst

    mock_eng_inst = MagicMock()
    mock_eng_inst.search.return_value = {"results": [], "latency_ms": 5, "reasoning_trace": None, "plan": None}
    mock_eng.return_value = mock_eng_inst

    from rat.ui.omnibar import OmnibarWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = OmnibarWindow()
    win.show_omnibar()
    app.processEvents()

    # 1. Ask Room C302
    win._submit_chat_prompt("phòng C302 ở đâu")
    app.processEvents()
    win.grab().save("scratch/test_live_reply_room.png")
    print("Saved test_live_reply_room.png")

    # 2. Angry state (teasing)
    win._submit_chat_prompt("đồ ngu")
    app.processEvents()
    win.grab().save("scratch/test_live_reply_angry.png")
    print("Saved test_live_reply_angry.png")

    # 3. Math calculation
    win._submit_chat_prompt("tính 150 * 4")
    app.processEvents()
    win.grab().save("scratch/test_live_reply_math.png")
    print("Saved test_live_reply_math.png")
