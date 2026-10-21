"""Re-run unchanged 327 selectors; preserve previous review output artifacts."""
import ast
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
import pytest


def selectors(path):
    tree = ast.parse(path.read_text())
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "TEST_FILES" for t in n.targets))


class PreservePriorReviewArtifacts:
    def pytest_collection_modifyitems(self, items):
        target = ROOT / "audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py"
        modules = {item.module for item in items if Path(item.module.__file__).resolve() == target}
        assert len(modules) == 1
        for module in modules:
            module.HERE = HERE


if __name__ == "__main__":
    files = selectors(HERE / "received_artifacts/run_consolidated.py")
    expected = selectors(ROOT / "audit/rat_overnight_sweep_codex_review_r6_20261020/received_artifacts/run_consolidated.py")
    expected.append("audit/rat_overnight_sweep_codex_review_r6_20261020/test_legacy_identity_and_real_history.py")
    assert files == expected
    os.environ.update(QT_QPA_PLATFORM="offscreen", RAT_REVIEW_R4_OUTPUT_DIR=str(HERE),
                      RAT_REVIEW_R5_OUTPUT_DIR=str(HERE), RAT_REVIEW_R6_OUTPUT_DIR=str(HERE),
                      RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE / "fake_session"))
    sys.exit(pytest.main(files + ["-q", f"--junitxml={HERE / 'regression.xml'}"],
                         plugins=[PreservePriorReviewArtifacts()]))
