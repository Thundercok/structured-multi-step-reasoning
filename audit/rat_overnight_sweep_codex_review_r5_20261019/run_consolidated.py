"""Run unchanged acceptance tests, redirecting r4's generated images into r5.

The r4 module writes two output artifacts to its HERE constant. Redirect that
constant after collection to preserve the previous review's immutable evidence.
No assertions or inputs are changed; both reviews contain the same real ledger.
"""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
import pytest


class PreservePriorReviewArtifacts:
    def pytest_collection_modifyitems(self, items):
        target = ROOT / "audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py"
        modules = {item.module for item in items if Path(item.module.__file__).resolve() == target}
        assert len(modules) == 1
        for module in modules:
            module.HERE = HERE


if __name__ == "__main__":
    received = json.loads((HERE / "received_artifacts/command.json").read_text())
    args = [arg for arg in received["argv"][3:] if not arg.startswith("--junitxml=")]
    args.append(f"--junitxml={HERE / 'regression.xml'}")
    os.environ.update(QT_QPA_PLATFORM="offscreen", RAT_REVIEW_R4_OUTPUT_DIR=str(HERE),
                      RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE / "fake_session"))
    sys.exit(pytest.main(args, plugins=[PreservePriorReviewArtifacts()]))
