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
    
    # 1. Compact default summon view
    win = OmnibarWindow()
    win.show_omnibar()
    app.processEvents()
    win.grab().save("scratch/live_chuot_compact.png")
    print("Saved scratch/live_chuot_compact.png")

    # 2. Speaking query reply
    win._submit_chat_prompt("phòng C302 ở đâu")
    app.processEvents()
    win.grab().save("scratch/live_chuot_room.png")
    print("Saved scratch/live_chuot_room.png")

    # 3. Teasing / Angry reply
    win._submit_chat_prompt("đồ ngu")
    app.processEvents()
    win.grab().save("scratch/live_chuot_angry.png")
    print("Saved scratch/live_chuot_angry.png")
