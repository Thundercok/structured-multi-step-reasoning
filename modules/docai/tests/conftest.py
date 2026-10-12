"""Allow explicit standalone tests without installing the module into RAT."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
