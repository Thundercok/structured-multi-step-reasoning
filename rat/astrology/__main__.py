"""Open the atlas without personal indexing, a background daemon or a model."""
import sys
from PyQt6.QtWidgets import QApplication
from rat.ui.natal_chart import NatalChartWindow


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RAT · Natal Atlas")
    window = NatalChartWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
