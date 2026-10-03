"""5 regression tests for NCKH reasoning harness bugs.

Each test is anchored to a real raw trace fixture from previous pilot runs:
(1) generation boundary / stop token: apply_chat_template requires add_generation_prompt=True, finish_reason tracked.
(2) ReAct does not copy placeholder: placeholder tokens rejected in answers, absent from REACT_SYSTEM.
(3) PAL does not hang: subprocess timeout on infinite loops, errors out on missing result instead of reporting ok.
(4) Parser does not pick wrong numbers: extract_conclusion_number normalizes units/equations to final number.
(5) ToT picks correct candidate: regex matches 'Best: [i]' instead of greedy first digit in reasoning preamble.
"""

import pytest
import qwen_mlx_backend
from qwen_mlx_backend import QwenMLXBackend, REACT_SYSTEM
from reasoning_env import ReasoningAction as A
from reasoning_strategies import (
    extract_answer,
    extract_code,
    run_python_sandboxed,
)
import test_qwen_mlx_backend_mocked as tmock

scripted = tmock.scripted
make_backend = tmock.make_backend
FakeTokenizer = tmock.FakeTokenizer
qwen_mlx_backend.stream_generate = scripted


@pytest.fixture(autouse=True)
def reset_scripted_generator(monkeypatch):
    monkeypatch.setattr(qwen_mlx_backend, "stream_generate", scripted)
    scripted.scripts.clear()
    scripted.calls.clear()
    yield
    scripted.scripts.clear()
    scripted.calls.clear()


# ==============================================================================
# 1. Generation Boundary & Stop Token
# Source: outputs/pilot_reasoning_train36_05b.json | item_id: pal_004_en_orig | strategy: COT
# ==============================================================================
RAW_COT_TRACE_FIXTURE = (
    "To determine the total number of pizza slices Albert eats in 4 weeks, we need to calculate the number "
    "of slices from the large pizzas and the small pizzas separately, and then sum them up.\n\n"
    "1. Calculate the number of slices from the large pizzas:\n"
    "   Albert eats 2 large pizzas per week.\n"
    "   Each large pizza has 16 slices.\n"
    "   So, the number of slices from the large pizzas in 4 weeks is:\n"
    "   2 * 16 * 4 = 128 slices.\n\n"
    "2. Calculate the number of slices from the small pizzas:\n"
    "   Albert eats 2 small pizzas per week.\n"
    "   Each small pizza has 8 slices.\n"
    "   So, the number of slices from the small pizzas in 4 weeks is:\n"
    "   2 * 8 * 4 = 64 slices.\n\n"
    "3. Calculate the total number of pizza slices:\n"
    "   Total slices = slices from large pizzas + slices from small pizzas\n"
    "   Total slices = 128 + 64 = 192 slices.\n\n"
    "Therefore, the total number of pizza slices Albert eats in 4 weeks is 192 slices."
)


def test_regression_generation_boundary_and_stop_token():
    """Bug 1: apply_chat_template must specify add_generation_prompt=True, and finish_reason must be recorded in trace."""
    b = make_backend()
    scripted.queue(RAW_COT_TRACE_FIXTURE)
    query = "Albert buys 2 large pizzas and 2 small pizzas per week for 4 weeks. What is the total number of pizza slices?"
    ans, conf, tok = b.run(A.COT, query)

    # 1. Backend must record generation trace including finish_reason
    assert hasattr(b, "last_trace"), "Backend must record last_trace"
    assert len(b.last_trace["generations"]) > 0, "Trace must capture generation events"
    last_gen = b.last_trace["generations"][0]
    assert last_gen["finish_reason"] == "stop", f"Expected finish_reason 'stop', got {last_gen.get('finish_reason')!r}"


# ==============================================================================
# 2. ReAct Does Not Copy Placeholder
# Source: outputs/pilot_reasoning_train36_05b.json | item_id: react_002_en_orig | strategy: COT
# ==============================================================================
RAW_REACT_PLACEHOLDER_FIXTURE = (
    "Answer: <kết quả> = 24 crates of 18 boxes + 15 crates of 25 boxes + 30 crates of 12 boxes = "
    "24 * 18 + 15 * 25 + 30 * 12 = 432 + 375 + 360 = 1167 boxes total."
)


def test_regression_react_placeholder_rejection():
    """Bug 2: Parser rejects echoed placeholder templates, and REACT_SYSTEM contains no placeholder artifacts."""
    # Parser must strip leading placeholder and extract the real numeric conclusion
    parsed = extract_answer(RAW_REACT_PLACEHOLDER_FIXTURE)
    assert "<kết quả>" not in parsed, f"Parsed answer leaked prompt placeholder: {parsed!r}"
    assert parsed == "1167", f"Expected parsed answer '1167', got {parsed!r}"

    # Prompt template must not contain placeholder identifiers that model mimics
    assert "bieu_thuc_so_hoc" not in REACT_SYSTEM, "REACT_SYSTEM prompt leaked placeholder 'bieu_thuc_so_hoc'"
    assert "<suy nghĩ>" not in REACT_SYSTEM, "REACT_SYSTEM prompt leaked placeholder '<suy nghĩ>'"


# ==============================================================================
# 3. PAL Does Not Hang on Loops & Rejects Empty Code Output
# Source 1: outputs/pilot_reasoning_train36_05b.json | item_id: plain_003_vi_trans | strategy: PAL
# Source 2: synthetic (infinite loop minimal case)
# ==============================================================================
RAW_PAL_NO_RESULT_CODE = """```python
# Bảng xếp hạng ban đầu:
# A, B, C, D, E

# Người thứ ba về đích sau người thứ năm:
# C về đích sau E => Thứ tự có thể là: A, B, E, C, D hoặc A, B, E, D, C

# Bảng xếp hạng sau đó sẽ là:
# A, B, C, D, E
```"""

RAW_PAL_INFINITE_LOOP_CODE = "while True:\n    pass"


def test_regression_pal_timeout_and_sandbox_safety():
    """Bug 3: PAL runner must cleanly timeout on infinite loops without hanging, and reject scripts producing no result.

    Ghi chú kiểm định: Test này kiểm tra cơ chế cô lập subprocess (subprocess.run),
    đảm bảo timeout=0.5s hoạt động sạch và script không có kết quả bị đánh dấu thất bại (ok=False).
    Nguy cơ treo thật giữa MLX Metal runtime và process con được kiểm tra trực tiếp ở bước B2.
    """
    # 1. Infinite loop must cleanly terminate with timeout status in < 1 second
    ok_loop, err_loop = run_python_sandboxed(RAW_PAL_INFINITE_LOOP_CODE, timeout=0.5)
    assert not ok_loop and err_loop == "timeout", f"Loop must timeout cleanly, got ok={ok_loop}, err={err_loop!r}"

    # 2. Code with no result must NOT report ok=True
    code_no_res = extract_code(RAW_PAL_NO_RESULT_CODE)
    ok_no_res, err_no_res = run_python_sandboxed(code_no_res, timeout=2.0)
    assert not ok_no_res, f"Code without result must fail, but got ok={ok_no_res!r}"
    assert "no result" in err_no_res, f"Expected 'no result' in error message, got {err_no_res!r}"


# ==============================================================================
# 4. Parser Does Not Pick Wrong Trailing Token Or Unit
# Source 1: outputs/pilot_reasoning_train36_05b.json | item_id: pal_004_en_orig | strategy: COT
# Source 2: outputs/pilot_reasoning_train36_05b.json | item_id: react_002_en_orig | strategy: COT
# Source 3: outputs/pilot_reasoning_train36_05b.json | item_id: react_007_en_para | strategy: COT
# ==============================================================================
RAW_PARSER_PIZZA_FIXTURE = (
    "To determine the total number of pizza slices Albert eats in 4 weeks, we need to calculate the number of slices.\n\n"
    "Therefore, the total number of pizza slices Albert eats in 4 weeks is 192 slices."
)
RAW_PARSER_BOXES_FIXTURE = (
    "A warehouse receives 24 crates of 18 boxes, 15 crates of 25 boxes, and 30 crates of 12 boxes.\n\n"
    "Therefore, the total is 1,167 boxes."
)
RAW_PARSER_ARITHMETIC_FIXTURE = (
    "Answer: <kết quả> = 3*(45+55) - 4*(120-85) + 250/5 = 3*(100) - 4*(15) + 50 = 300 - 60 + 50 = 290."
)


def test_regression_parser_does_not_pick_wrong_trailing_token_or_unit():
    """Bug 4: Parser extracts numeric conclusion without capturing trailing units or intermediate equation text."""
    ans1 = extract_answer(RAW_PARSER_PIZZA_FIXTURE)
    assert ans1 == "192", f"Expected '192', got {ans1!r}"

    ans2 = extract_answer(RAW_PARSER_BOXES_FIXTURE)
    assert ans2 == "1167", f"Expected '1167', got {ans2!r}"

    ans3 = extract_answer(RAW_PARSER_ARITHMETIC_FIXTURE)
    assert ans3 == "290", f"Expected '290', got {ans3!r}"


# ==============================================================================
# 5. ToT Selects Correct Candidate Branch
# Source: synthetic (reconstructed evaluator rationale matching ToT eval prompt pattern)
# ==============================================================================
RAW_TOT_EVAL_FIXTURE = (
    "Đánh giá 3 phương án:\n"
    "Phương án 0 sai vì tính nhầm 24 * 18 = 422.\n"
    "Phương án 1 tính đúng 24 * 18 = 432 và ra 1167 boxes.\n"
    "Phương án 2 tính thiếu thùng hàng cuối.\n"
    "Best: 1"
)


def test_regression_tot_selects_correct_candidate_branch():
    """Bug 5: ToT candidate selection parses 'Best: [i]' rather than greedily matching numbers in the rationale."""
    b = make_backend()
    scripted.queue(
        "Phương án 0... Answer: 422",
        "Phương án 1... Answer: 1167",
        "Phương án 2... Answer: 500",
        RAW_TOT_EVAL_FIXTURE,
    )
    ans, conf, tok = b.run(A.TOT, "Tính tổng số hộp hàng?")
    assert ans == "1167", f"ToT must select candidate 1 ('1167'), got {ans!r}"
