"""Re-run 372 submitted tests plus the original 26 Codex probes, preserving prior artifacts."""
import importlib.util,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'audit/rat_cot_runtime_acceptance_20261020'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
spec=importlib.util.spec_from_file_location('submitted_runner',SOURCE/'run_consolidated.py')
submitted=importlib.util.module_from_spec(spec);spec.loader.exec_module(submitted)
submitted.HERE=HERE
for name in ('fake_session','fake_history_halt','locked_ledger_replay','legacy_fake_history_halt','same_document_legacy_fake','received_artifacts'):
    if (SOURCE/name).is_dir():shutil.copytree(SOURCE/name,HERE/name,dirs_exist_ok=True)
for name in ('fake_session','fake_history_halt','locked_ledger_replay','legacy_fake_history_halt','same_document_legacy_fake'):
    shutil.copy2(SOURCE/f'{name}.txt',HERE/f'{name}.txt')
os.environ.update(QT_QPA_PLATFORM='offscreen',RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE/'fake_session'),**{f'RAT_REVIEW_R{i}_OUTPUT_DIR':str(HERE) for i in (4,5,6,7)})
import pytest
prior=['audit/rat_cot_runtime_codex_review_20261020/test_contract_probes.py','audit/rat_cot_runtime_codex_review_20261020/test_replay_fixture_probe.py']
sys.exit(pytest.main(submitted.ALL_TEST_FILES+prior+['-q',f'--junitxml={HERE/"baseline.xml"}'],plugins=[submitted.PreservePriorReviewArtifacts()]))
