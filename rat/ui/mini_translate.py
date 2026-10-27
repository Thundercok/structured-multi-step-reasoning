"""Compatibility entry point; translation business logic lives in shared capabilities."""
from rat.os.mini_hotkey import register_hotkey

def main():
    from rat.ui.mini_quick import main as run
    run()

if __name__ == "__main__":
    main()
