"""One bounded check of runtime fixes plus the existing RAT request/UI bridge."""
import importlib.util, os, sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT)); os.chdir(ROOT)
os.environ['QT_QPA_PLATFORM']='offscreen'
spec=importlib.util.spec_from_file_location('submitted_fixture_adapter', HERE/'received_runtime/redirect_plugin.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
adapter.PROBE_OUTPUTS=HERE/'historical_probe_outputs'
class PreserveHistoricalEvidence:
    def pytest_collection_modifyitems(self,items):
        selected=[item for item in items if Path(item.module.__file__).parent.name.startswith('rat_cot_runtime_codex_review_r')]
        # r2's legacy fake _chat now has explicit failed-generation facts.
        # Use the submitted versioned fixture adapter, never alter production.
        adapter.pytest_collection_modifyitems(selected)
import pytest
files=[
    'tests/test_execution_flow.py',
    'tests/test_flow_interaction.py::test_composer_reaches_composed_policy_and_returns_to_same_conversation',
    'audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py',
    'audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py',
    'audit/rat_cot_runtime_codex_review_r4_20261021/test_remaining_contracts.py',
    'audit/rat_cot_runtime_codex_review_r5_20261021/test_binding_and_dispatch.py',
    'audit/rat_cot_runtime_codex_review_r6_20261021/test_trace_and_calibrator.py',
    'tests/test_research_study.py','test_optimal_stopping.py','test_entry_predictor.py',
]
sys.exit(pytest.main(files+['-q',f'--junitxml={HERE/"current_contracts.xml"}'],plugins=[PreserveHistoricalEvidence()]))
