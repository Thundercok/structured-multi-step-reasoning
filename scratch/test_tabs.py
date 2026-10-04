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
    win = OmnibarWindow()
    win.show()
    win.set_expanded(True)
    app.processEvents()

    # Files view
    win.switch_section(1)
    app.processEvents()
    time.sleep(0.05)
    win.grab().save("scratch/live_tab_files.png")

    # Schedule view
    win.switch_section(2)
    app.processEvents()
    time.sleep(0.05)
    win.grab().save("scratch/live_tab_schedule.png")

    # Club view
    win.switch_section(3)
    app.processEvents()
    time.sleep(0.05)
    win.grab().save("scratch/live_tab_club.png")

    print("All tabs saved successfully!")
