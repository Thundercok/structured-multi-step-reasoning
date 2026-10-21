"""Re-run the unchanged 319 selectors against reviewer-generated fake artifacts.

Redirect only r4's image/geometry output path, preserving old audit evidence.
"""
import ast
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
    tree = ast.parse((HERE / "received_artifacts/run_consolidated.py").read_text())
    selectors = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "TEST_FILES" for t in n.targets))
    previous = json.loads((ROOT / "audit/rat_overnight_sweep_codex_review_r5_20261019/received_artifacts/command.json").read_text())
    expected = [a for a in previous["argv"][3:] if a != "-q" and not a.startswith("--junitxml=")]
    expected.append("audit/rat_overnight_sweep_codex_review_r5_20261019/test_provenance_and_conclusion.py")
    assert selectors == expected, "Consolidated selectors changed since independent r5"
    os.environ.update(QT_QPA_PLATFORM="offscreen", RAT_REVIEW_R4_OUTPUT_DIR=str(HERE),
                      RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE / "fake_session"),
                      RAT_REVIEW_R5_OUTPUT_DIR=str(HERE))
    sys.exit(pytest.main(selectors + ["-q", f"--junitxml={HERE / 'regression.xml'}"],
                         plugins=[PreservePriorReviewArtifacts()]))
