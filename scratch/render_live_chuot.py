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

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Compact HUD view (Single unified card with peeking mascot on top bezel)
    win = OmnibarWindow()
    win.show()
    app.processEvents()
    time.sleep(0.1)
    app.processEvents()
    win.grab().save("scratch/live_chuot_compact.png")
    print("Saved live_chuot_compact.png")

    # 2. Speaking state: Pop-out xéo (+10° tilt) + Floating Speech Bubble with Vector Tail
    win.set_mascot_speaking("Nghe đây. Cần tìm phòng C302 hay xem lịch hôm nay?")
    for _ in range(12):
        app.processEvents()
        time.sleep(0.04)
    win.grab().save("scratch/live_chuot_convo.png")
    print("Saved live_chuot_convo.png")

    # 3. Deadpan Room response
    win.speech_bubble.set_reply("Phòng C302: Tầng 3, Tòa C. Rẽ trái từ thang máy.")
    app.processEvents()
    win.grab().save("scratch/live_chuot_room.png")
    print("Saved live_chuot_room.png")

    # 4. Expanded Notebook view
    win.set_expanded(True)
    for _ in range(8):
        app.processEvents()
        time.sleep(0.03)
    win.grab().save("scratch/live_chuot_expanded.png")
    print("Saved live_chuot_expanded.png")

    win.close()
    print("All live Chuột screenshots saved successfully!")
