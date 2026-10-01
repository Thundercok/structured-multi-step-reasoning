import sys
import os
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from rat.ui.omnibar import OmnibarWindow
from rat.ui.chat_stream import get_mascot_pixmap

def main():
    app = QApplication.instance() or QApplication(sys.argv)

    for size, top_m in [(155, 116), (165, 122), (180, 134), (205, 150)]:
        w = OmnibarWindow()
        w.mascot_peeking.setFixedSize(size, size)
        w.mascot_peeking.setPixmap(get_mascot_pixmap(size, size, bust_only=True))
        w.mascot_peeking.move(36, 2)
        w.centralWidget().layout().setContentsMargins(16, top_m, 16, 16)
        
        # 1. Compact
        w.resize(652, top_m + 88)
        w.show()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        w.grab().save(f"scratch/eval_compact_{size}.png")
        
        # 2. Expanded Convo
        w.set_expanded(True)
        w.resize(652, top_m + 470)
        w.chat_composer_input.setText("Phòng C302 ở đâu?")
        w.chat_stream.add_user_message("Phòng C302 ở đâu?")
        w.chat_stream.add_assistant_message(
            "Tầng 3, Tòa C. Rẽ trái từ thang máy.",
            steps=["Xác định vị trí phòng C302", "Tra cứu sơ đồ cơ sở"],
            latency_ms=12.4,
            strategy_badge="⚡ Room Locator"
        )
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        w.grab().save(f"scratch/eval_expanded_{size}.png")
        w.close()
        
    print("SUCCESS: Generated all size evaluations")

if __name__ == "__main__":
    main()
