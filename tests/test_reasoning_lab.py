import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QGuiApplication
import pytest

from rat.engine.measured_ladder import (MODE_COMPARE, MODE_LADDER, MODE_POLICY, TAU_COT, TAU_DIRECT,
                                        append_log, entry_reason, solve)
from rat.ui.reasoning_lab import EXAMPLES, ReasoningLabController, create_view, present_run


class FakeBackend:
    model_id = "fake-model"

    def __init__(self, replies):
        self.replies = replies
        self.calls = []
        self.last_trace = {}

    def run(self, strategy, query, **kwargs):
        name = strategy.name
        self.calls.append(name)
        answer, confidence, tokens = self.replies[name]
        tools = []
        if name == "PAL":
            tools = [{"name": "python", "input": "result = 2 + 2", "ok": True, "output": answer}]
        self.last_trace = {"generations": [{"output": f"{name} output", "prompt_tokens": 7}], "tools": tools}
        return answer, confidence, tokens


REPLIES = {"DIRECT": ("1", 0.5, 10), "COT": ("2", 0.5, 20), "PAL": ("4", 0.9, 30)}


def test_entry_rule_uses_the_measured_word_cutoff():
    assert entry_reason("một câu ngắn")[0] == "PAL"
    assert entry_reason(" ".join(["từ"] * 81))[0] == "DIRECT"
    assert entry_reason(" ".join(["từ"] * 80))[0] == "PAL"


def test_policy_routes_short_question_straight_to_pal():
    backend = FakeBackend(REPLIES)
    run = solve(backend, "hai cộng hai", MODE_POLICY)
    assert backend.calls == ["PAL"]
    assert run.final_strategy == "PAL" and run.final_answer == "4"
    assert run.steps[0].code == "result = 2 + 2" and run.steps[0].tool_ok is True


def test_ladder_stops_at_first_confident_rung():
    replies = {**REPLIES, "DIRECT": ("1", TAU_DIRECT, 10)}
    backend = FakeBackend(replies)
    run = solve(backend, "câu hỏi", MODE_LADDER)
    assert backend.calls == ["DIRECT"] and run.path == ["DIRECT"]
    assert "dừng ở đây" in run.steps[0].decision


def test_ladder_escalates_to_cot_then_stops_on_threshold():
    replies = {**REPLIES, "COT": ("2", TAU_COT, 20)}
    backend = FakeBackend(replies)
    run = solve(backend, "câu hỏi", MODE_LADDER)
    assert backend.calls == ["DIRECT", "COT"]
    assert "chạy thêm" in run.steps[0].decision
    assert run.final_answer == "2" and run.tokens == 30 and run.prompt_tokens == 14


def test_ladder_ends_at_pal_when_confidence_stays_low():
    backend = FakeBackend(REPLIES)
    run = solve(backend, "câu hỏi", MODE_LADDER)
    assert run.path == ["DIRECT", "COT", "PAL"] and run.final_strategy == "PAL"


def test_compare_runs_every_strategy_without_choosing():
    backend = FakeBackend(REPLIES)
    run = solve(backend, "câu hỏi", MODE_COMPARE)
    assert backend.calls == ["DIRECT", "COT", "PAL"]
    assert run.final_answer == "" and run.final_strategy == ""


def test_pal_float_artifact_is_repaired_for_the_answer_but_not_the_tool_output():
    replies = {**REPLIES, "PAL": ("11.000000000000002", 0.9, 30)}
    run = solve(FakeBackend(replies), "câu hỏi", MODE_POLICY)
    assert run.final_answer == "11"
    assert run.steps[0].tool_output == "11.000000000000002"


def test_cancelled_run_is_reported_and_keeps_finished_steps():
    class CancelsAtCot(FakeBackend):
        def run(self, strategy, query, **kwargs):
            if strategy.name == "COT":
                raise RuntimeError("Cooperative cancellation before generation start")
            return super().run(strategy, query, **kwargs)

    run = solve(CancelsAtCot(REPLIES), "câu hỏi", MODE_LADDER)
    assert run.status == "cancelled" and run.path == ["DIRECT"]
    assert run.reason == "Đã dừng theo yêu cầu."


def test_backend_failure_is_reported_not_raised():
    class Broken(FakeBackend):
        def run(self, strategy, query, **kwargs):
            raise ValueError("boom")

    run = solve(Broken(REPLIES), "câu hỏi", MODE_POLICY)
    assert run.status == "failed" and "boom" in run.reason


def test_log_appends_one_json_line_per_run(tmp_path):
    path = tmp_path / "nested" / "runs.jsonl"
    run = solve(FakeBackend(REPLIES), "câu hỏi", MODE_LADDER)
    append_log(run, path, model_id="fake-model")
    append_log(run, path, model_id="fake-model")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["path"] == ["DIRECT", "COT", "PAL"] and rows[0]["tokens"] == 60
    assert rows[0]["model_id"] == "fake-model" and rows[0]["question"] == "câu hỏi"


def test_present_run_marks_correctness_only_when_the_answer_is_known():
    run = solve(FakeBackend(REPLIES), "câu hỏi", MODE_POLICY)
    assert present_run(run)["finalVerdict"] == ""
    assert present_run(run, "4")["finalVerdict"] == "correct"
    assert present_run(run, "5")["finalVerdict"] == "wrong"


@pytest.fixture(scope="module")
def app():
    yield QGuiApplication.instance() or QGuiApplication([])


def wait_until(predicate, timeout_ms=5000):
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: predicate() and loop.quit())
    poll.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    poll.stop()
    assert predicate()


def test_window_loads_runs_an_example_and_logs_it(app, tmp_path):
    log_path = tmp_path / "runs.jsonl"
    controller = ReasoningLabController(lambda: FakeBackend(REPLIES), log_path=log_path)
    view = None
    try:
        view = create_view(controller, dark_mode=False)
        controller.useExample(0)
        assert controller.snapshot["question"] == EXAMPLES[0]["text"]
        controller.setMode("ladder")
        controller.submit()
        wait_until(lambda: not controller.snapshot["busy"])
        result = controller.snapshot["result"]
        assert result["status"] == "completed" and len(result["steps"]) == 3
        assert result["finalVerdict"] == "wrong"
        assert log_path.is_file()
    finally:
        if view is not None:
            view.close()
        controller.close()


def test_editing_the_question_clears_the_known_answer(app, tmp_path):
    controller = ReasoningLabController(lambda: FakeBackend(REPLIES), log_path=tmp_path / "runs.jsonl")
    try:
        controller.useExample(1)
        controller.editQuestion("một câu khác")
        controller.submit()
        wait_until(lambda: not controller.snapshot["busy"])
        assert controller.snapshot["result"]["finalVerdict"] == ""
    finally:
        controller.close()


def test_startup_failure_shows_an_error_and_allows_retry(app, tmp_path):
    def broken():
        raise OSError("model missing")

    controller = ReasoningLabController(broken, log_path=tmp_path / "runs.jsonl")
    try:
        controller.editQuestion("câu hỏi")
        controller.submit()
        wait_until(lambda: not controller.snapshot["busy"])
        assert "model missing" in controller.snapshot["error"]
    finally:
        controller.close()
