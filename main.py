"""
main.py — Launch rat (Smart File Finder, AI Assistant & PDF Desk).
Run GUI: python main.py                       (Unified Qt Quick Desk)
         python main.py quick-pdf             (Quick PDF mode)
         python main.py widgets               (Legacy Widgets Omnibar compatibility)
Run CLI: python main.py search "file word tuần trước"
         python main.py index
         python main.py status
"""

import sys
from rat.main import main

if __name__ == "__main__":
    main()
