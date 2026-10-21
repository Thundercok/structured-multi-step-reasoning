"""Exercise the actual Qwen strategy methods with a scripted generation seam.

Model construction, mlx imports and real generation are excluded. Strategy run,
COT/SC loops and trace resets come from the unchanged backend AST.
"""
import ast
import json
from pathlib import Path
import types
import numpy as np
import pytest
from reasoning.bundle import create_synthetic_specimen_bundle
from reasoning.runtime import OnlineReasoningController

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def source_backend(*,fail_dispatch=None,confidence=.1):
    path=ROOT/'qwen_mlx_backend.py'
    tree=ast.parse(path.read_text(),filename=str(path))
    # Exclude MLX-dependent imports. __main__ stays inactive under this namespace.
    tree.body=[node for node in tree.body if not (isinstance(node,ast.ImportFrom) and (node.module or '').startswith('mlx'))]
    namespace={'__name__':'offline_qwen_source_replay'}
    exec(compile(tree,str(path),'exec'),namespace)
    cls=namespace['QwenMLXBackend']
    backend=object.__new__(cls)  # Never call __init__/load/model weights.
    backend.hidden_size=2;backend.max_tokens=20;backend.prompt_profile='legacy'
    backend.embed=lambda query:np.zeros(2,dtype=np.float32)
    counters={'dispatched':0,'successful':0,'tokens':0}
    def scripted_chat(self,messages,**kwargs):
        counters['dispatched']+=1
        if counters['dispatched']==fail_dispatch:
            raise RuntimeError('scripted generation exception after dispatch')
        counters['successful']+=1;counters['tokens']+=20
        # Matches qwen_mlx_backend._chat: only completed generations, key tokens.
        self.last_trace['generations'].append({'messages':messages,'tokens':20,'prompt_tokens':9,'output':'Answer: 1','finish_reason':'eos'})
        return 'Answer: 1',confidence,20
    backend._chat=types.MethodType(scripted_chat,backend)
    bundle,policy=create_synthetic_specimen_bundle()
    return backend,counters,OnlineReasoningController(backend,policy,bundle=bundle,allow_synthetic_bundle=True)


def test_actual_qwen_strategy_failure_preserves_generation_costs():
    backend,counters,controller=source_backend(fail_dispatch=4)
    with pytest.raises(RuntimeError) as caught:controller.solve('authored synthetic arithmetic fixture')
    ledger=caught.value.cost_ledger
    evidence={'counters':counters,'current_trace':backend.last_trace,'ledger':ledger.__dict__}
    (HERE/'qwen_failure_case.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert (ledger.underlying_requests_dispatched,ledger.underlying_requests_succeeded,ledger.underlying_requests_failed,ledger.generated_tokens)==(4,3,1,60),evidence


def test_actual_qwen_cot_does_not_underreport_over_budget_generation():
    backend,counters,controller=source_backend(confidence=.99)
    result=controller.solve('authored synthetic arithmetic fixture',max_generated_tokens=1)
    evidence={'counters':counters,'current_trace':backend.last_trace,'ledger':result.cost_ledger.__dict__}
    (HERE/'qwen_token_cap_case.json').write_text(json.dumps(evidence,indent=2)+'\n')
    assert result.cost_ledger.generated_tokens==counters['tokens'],evidence


def test_control_actual_qwen_cot_without_cap():
    _,counters,controller=source_backend(confidence=.99)
    result=controller.solve('authored synthetic arithmetic fixture')
    assert result.status=='completed'
    assert result.generated_tokens==counters['tokens']==20
    assert result.cost_ledger.underlying_requests_dispatched==1
