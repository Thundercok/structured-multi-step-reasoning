import sys
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from rat.ui.omnibar import OmnibarWindow

app = QApplication.instance() or QApplication(sys.argv)
win = OmnibarWindow()
win.show()
app.processEvents()

# Send prompt and expand
win.set_expanded(True)
win._submit_chat_prompt("Thứ 4 tuần này tui có môn gì không Rat?")
app.processEvents()
win.grab().save("scratch/live_game_companion_convo.png")

win.close()
print("Convo screenshot saved successfully!")
