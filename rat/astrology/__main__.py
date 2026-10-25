"""Open the atlas via the unified QtQuick Desk."""
import sys
from rat.ui.quick_app import main as quick_main


def main():
    sys.exit(quick_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
