from reasoning_strategies import (
    extract_answer, extract_number, numeric_match, parse_action,
    majority_vote, safe_calculate, run_python_sandboxed, extract_code,
)


def test_extract_answer_prefers_last_answer_line():
    text = "Bước 1: ...\nAnswer: 42 (nháp)\nkiểm tra lại...\nAnswer: 44"
    assert extract_answer(text) == "44"


def test_extract_answer_fallback_last_line():
    assert extract_answer("không có nhãn nào cả\nkết quả là 7") == "kết quả là 7"


def test_numeric_match_handles_formatting():
    assert numeric_match("Answer: 1,234.5 dong", "1234.5")
    assert numeric_match("ket qua = -3", "-3.0000")
    assert not numeric_match("5", "6")


def test_parse_action_calculate_and_finish():
    assert parse_action("Thought: x\nAction: calculate[12*7]") == ("calculate", "12*7")
    assert parse_action("Action: finish[42]") == ("finish", "42")
    assert parse_action("không có action") is None


def test_majority_vote():
    vote, ratio = majority_vote(["12", "12", "13", "12"])
    assert vote == "12" and abs(ratio - 0.75) < 1e-9
    assert majority_vote([]) == ("", 0.0)


def test_safe_calculate_arithmetic():
    assert safe_calculate("2 + 3 * 4") == "14"
    assert safe_calculate("(10 - 4) / 2") == "3.0"
    assert safe_calculate("2 ** 10") == "1024"


def test_safe_calculate_blocks_injection():
    for expr in ["__import__('os').system('echo hi')", "open('/etc/passwd')", "[].__class__"]:
        assert safe_calculate(expr).startswith("error")


def test_extract_code_from_fence_and_raw():
    fenced = "giải thích...\n```python\nresult = 1 + 1\n```\nxong"
    assert extract_code(fenced) == "result = 1 + 1"
    assert extract_code("result = 5") == "result = 5"


def test_sandbox_runs_simple_code():
    ok, out = run_python_sandboxed("result = sum(range(1, 11))")
    assert ok and out == "55"


def test_sandbox_blocks_import_and_filesystem():
    ok, out = run_python_sandboxed("import os\nresult = os.listdir('.')")
    assert not ok and "blocked" in out


def test_sandbox_catches_runtime_error():
    ok, out = run_python_sandboxed("result = 1 / 0")
    assert not ok and "ZeroDivisionError" in out


def test_sandbox_timeout():
    ok, out = run_python_sandboxed("while True: pass", timeout=1.0)
    assert not ok and out == "timeout"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
