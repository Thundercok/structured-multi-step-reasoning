import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint

# Offscreen
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from rat.ui.omnibar import OmnibarWindow

app = QApplication.instance() or QApplication(sys.argv)
out_dir = Path("scratch/rat_polish_validation")
out_dir.mkdir(exist_ok=True, parents=True)

win = OmnibarWindow()
win.show()

# Turn 1
win._submit_chat_prompt("Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này thêm 12 tín chỉ điểm 8.5 thì CPA mới là bao nhiêu?")
app.processEvents()

# Expand to show conversation ribbon and assistant card
win.set_expanded(True)
app.processEvents()

# Capture expanded
pix_expanded = win.grab()
pix_expanded.save(str(out_dir / "expanded_with_ribbon.png"))

# Test mascot thinking with glasses
win.mascot_peeking.set_state("thinking")
app.processEvents()
pix_mascot = win.mascot_peeking.grab()
pix_mascot.save(str(out_dir / "mascot_thinking_glasses.png"))

# Collapse to compact and open reader to check session tag
win.set_expanded(False)
win.set_reply_reader_open(True)
app.processEvents()
pix_reader = win.grab()
pix_reader.save(str(out_dir / "compact_reader_with_tag.png"))

print("Screenshots saved to", out_dir)
win.close()
