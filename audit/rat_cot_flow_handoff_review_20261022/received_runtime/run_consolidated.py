"""Run consolidated acceptance suite for rat_cot_runtime_acceptance_20261020.

Runs the prior 331 tests + 41 new runtime acceptance, bundle, and readiness tests.
Preserves prior immutable audit artifacts by redirecting output directories.
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
        for item in items:
            mod = getattr(item, "module", None)
            if mod is None:
                continue
            p = Path(getattr(mod, "__file__", "")).resolve()
            if "audit/" in str(p):
                mod.HERE = HERE


PRIOR_331_TEST_FILES = [
    "tests/test_progressive_search.py",
    "tests/test_mlx_document_session.py",
    "tests/test_selected_document_qa.py",
    "tests/test_selected_document_ui.py",
    "tests/test_workbench_scene.py",
    "tests/test_rat_completion_reconciliation.py",
    "tests/test_rat_completion_boundaries.py",
    "tests/test_document_model_startup.py",
    "tests/test_rat_magic_ui.py",
    "tests/test_research_study.py",
    "test_optimal_stopping.py",
    "test_entry_predictor.py",
    "tests/test_assistant_runtime.py",
    "tests/test_rat_headless_cli.py",
    "tests/test_resident_warmup.py",
    "audit/rat_finder_codex_review_20261016/test_finder_integration_probes.py",
    "audit/rat_finder_codex_review_r2_20261017/test_keyboard_followups.py",
    "audit/rat_milestones_abc_independent_review_20261018/test_review_probes.py",
    "audit/rat_milestones_abc_independent_review_20261018/test_ui_review_probes.py",
    "audit/rat_milestones_abc_review_r2_20261018/test_additional_headless.py",
    "audit/rat_milestones_abc_review_r2_20261018/test_additional_ui.py",
    "audit/rat_milestones_abc_review_r3_20261019/test_slide_summary_projection.py",
    "audit/rat_overnight_sweep_codex_review_20261019/test_visual_acceptance.py",
    "audit/rat_overnight_sweep_repair_codex_review_20261019/test_followup_acceptance.py",
    "tests/test_crash_shield.py",
    "tests/test_harness_regressions.py",
    "audit/rat_overnight_sweep_codex_review_r3_20261019/test_remaining_probes.py",
    "audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py",
    "audit/rat_overnight_sweep_codex_review_r5_20261019/test_provenance_and_conclusion.py",
    "audit/rat_overnight_sweep_codex_review_r6_20261020/test_legacy_identity_and_real_history.py",
    "audit/rat_overnight_sweep_codex_review_r7_20261020/test_failed_request_reporting.py",
]

NEW_RUNTIME_ACCEPTANCE_TEST_FILES = [
    "tests/test_online_reasoning.py",
    "tests/test_policy_bundle.py",
    "tests/test_online_reasoning_execution.py",
    "tests/test_native_acceptance_readiness.py",
]

ALL_TEST_FILES = PRIOR_331_TEST_FILES + NEW_RUNTIME_ACCEPTANCE_TEST_FILES

if __name__ == "__main__":
    args = list(ALL_TEST_FILES) + ["-q", f"--junitxml={HERE / 'regression.xml'}"]
    os.environ.update(
        QT_QPA_PLATFORM="offscreen",
        RAT_REVIEW_R4_OUTPUT_DIR=str(HERE),
        RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE / "fake_session"),
        RAT_REVIEW_R5_OUTPUT_DIR=str(HERE),
        RAT_REVIEW_R6_OUTPUT_DIR=str(HERE),
        RAT_REVIEW_R7_OUTPUT_DIR=str(HERE),
    )
    sys.exit(pytest.main(args, plugins=[PreservePriorReviewArtifacts()]))
