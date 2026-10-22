"""Current regression plus immutable r2/r3/r4/r5 probes; all output stays in r6."""
import importlib.util, os, shutil, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'audit/rat_cot_runtime_acceptance_20261020'
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location('submitted_r5_runner', SOURCE / 'run_consolidated.py')
submission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(submission)
shutil.copy2(SOURCE / 'legacy_fake_calls.jsonl', HERE / 'legacy_fake_calls.jsonl')
for name in ('fake_session', 'fake_history_halt', 'locked_ledger_replay', 'legacy_fake_history_halt', 'same_document_legacy_fake'):
    if (SOURCE / name).is_dir():
        shutil.copytree(SOURCE / name, HERE / name, dirs_exist_ok=True)
    shutil.copy2(SOURCE / f'{name}.txt', HERE / f'{name}.txt')
os.environ.update(QT_QPA_PLATFORM='offscreen', RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE / 'fake_session'), **{f'RAT_REVIEW_R{i}_OUTPUT_DIR': str(HERE) for i in (4, 5, 6, 7)})
class PreserveHistoricalEvidence:
    def pytest_collection_modifyitems(self, items):
        for module in {item.module for item in items}:
            path = Path(module.__file__).resolve()
            if 'audit' not in path.relative_to(ROOT).parts:
                continue
            if path.parent.name.startswith('rat_cot_runtime_codex_review_r'):
                dest = HERE / 'prior_probe_outputs' / path.parent.name
                dest.mkdir(parents=True, exist_ok=True)
                module.HERE = dest
                if hasattr(module, "helper"):
                    module.helper.HERE = dest
            else:
                module.HERE = HERE
import pytest
files = submission.ALL_TEST_FILES + [
    'audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py',
    'audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py',
    'audit/rat_cot_runtime_codex_review_r4_20261021/test_remaining_contracts.py',
    'audit/rat_cot_runtime_codex_review_r5_20261021/test_binding_and_dispatch.py',
]
sys.exit(pytest.main(files + ['-q', f'--junitxml={HERE / "baseline.xml"}'], plugins=[PreserveHistoricalEvidence()]))
