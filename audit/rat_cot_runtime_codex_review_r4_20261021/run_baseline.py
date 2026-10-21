"""372 current regression cases + 19 r3 contracts + 3 r2 native replay controls.
Legacy contradictory hard-cap probes remain immutable and are not acceptance gates.
"""
import importlib.util,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;SOURCE=ROOT/'audit/rat_cot_runtime_acceptance_20261020'
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT));os.chdir(ROOT)
spec=importlib.util.spec_from_file_location('submitted_runner',SOURCE/'run_consolidated.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
for name in ('fake_session','fake_history_halt','locked_ledger_replay','legacy_fake_history_halt','same_document_legacy_fake','received_artifacts'):
    if (SOURCE/name).is_dir():shutil.copytree(SOURCE/name,HERE/name,dirs_exist_ok=True)
for name in ('fake_session','fake_history_halt','locked_ledger_replay','legacy_fake_history_halt','same_document_legacy_fake'):
    shutil.copy2(SOURCE/f'{name}.txt',HERE/f'{name}.txt')
os.environ.update(QT_QPA_PLATFORM='offscreen',RAT_REVIEW_FAKE_OUTPUT_DIR=str(HERE/'fake_session'),**{f'RAT_REVIEW_R{i}_OUTPUT_DIR':str(HERE) for i in (4,5,6,7)})
class RedirectAuditWriters:
    def pytest_collection_modifyitems(self,items):
        for mod in {item.module for item in items}:
            p=Path(mod.__file__).resolve()
            if p==ROOT/'audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py':mod.HERE=HERE
            if p in (ROOT/'audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py',ROOT/'audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py'):
                dest=HERE/'prior_probe_outputs'/p.parent.name;dest.mkdir(parents=True,exist_ok=True);mod.HERE=dest
import pytest
files=m.ALL_TEST_FILES+['audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py','audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py']
sys.exit(pytest.main(files+['-q',f'--junitxml={HERE/"baseline.xml"}'],plugins=[RedirectAuditWriters()]))
