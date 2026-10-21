"""
main.py — Launch rat (Smart File Finder & Spotlight Assistant).
Run GUI: python main.py
Run CLI: python main.py search "file word tuần trước"
         python main.py index
         python main.py status
"""

import sys
from rat.os.crash_shield import install_crash_shield
from rat.main import main

if __name__ == "__main__":
    install_crash_shield()
    main()
