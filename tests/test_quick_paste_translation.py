"""A long foreign passage in the composer is translated without calling a model."""
import threading

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtTest import QTest

from rat.ui.quick_pdf_controller import offers_find_or_translate
from tests.test_quick_unified_flow import app, quick_env, wait_for  # noqa: F401

PASSAGE = ("Attention mechanisms allow a neural network to focus on the most relevant parts of its input "
           "when producing each element of the output, which has transformed machine translation research.")
VIETNAMESE = ("Mình muốn hỏi là trong kỳ này nếu mình học thêm hai môn tự chọn nữa thì có bị vượt quá số tín "
              "chỉ tối đa mà nhà trường cho phép hay không vậy?")


class FakeTranslator:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def translate(self, text, source="auto", target="vi"):
        self.calls.append(text)
        if self.error:
            raise self.error
        return {"text": "Bản dịch tiếng Việt.", "source_language": "en"}


def press_return(env, text):
    editor = env.root.findChild(QQuickItem, "draftEditor")
    editor.setProperty("text", text)
    editor.forceActiveFocus()
    QTest.qWait(30)
    QTest.keyClick(env.view, Qt.Key.Key_Return)
    return editor


def test_foreign_passage_translates_without_a_model_and_clears_the_composer(quick_env):
    control = quick_env.controller
    control._translator = FakeTranslator()
    editor = press_return(quick_env, PASSAGE)

    wait_for(lambda: control.snapshot["view"] == "answer")
    assert control._translator.calls == [PASSAGE]
    assert control._last_assistant_answer == "Bản dịch tiếng Việt."
    assert editor.property("text") == ""
    assert quick_env.backend.run_calls == []


def test_failed_translation_keeps_the_draft_and_can_be_retried(quick_env):
    control = quick_env.controller
    control._translator = FakeTranslator(OSError("model missing"))
    editor = press_return(quick_env, PASSAGE)

    wait_for(lambda: "Chuột chưa dịch được" in (control.snapshot["status"] or ""))
    assert editor.property("text") == PASSAGE
    assert not control._composer_translation

    control._translator = FakeTranslator()
    QTest.keyClick(quick_env.view, Qt.Key.Key_Return)
    wait_for(lambda: control.snapshot["view"] == "answer")
    assert editor.property("text") == ""


def test_pressing_return_twice_translates_once(quick_env):
    control = quick_env.controller
    control._translator = FakeTranslator()
    control._composer_translation = True
    press_return(quick_env, PASSAGE)
    QTest.qWait(50)
    assert control._translator.calls == []


def test_what_counts_as_a_foreign_passage(quick_env):
    control = quick_env.controller
    assert control.isForeignPassage(PASSAGE)
    assert control.isForeignPassage("Attention is all you need.\nIt changed machine translation research.")
    assert not control.isForeignPassage(VIETNAMESE)
    assert not control.isForeignPassage("what is binary search?")
    assert not control.isForeignPassage("/Users/me/a.pdf\n/Users/me/b.pdf")
    assert not control.isForeignPassage("")


def test_passage_with_a_selected_document_is_a_question_about_it(quick_env):
    control = quick_env.controller
    control._selection = object()
    assert not control.isForeignPassage(PASSAGE)
    control._selection = None
    control._assistant_sources = [{"name": "a.txt"}]
    assert not control.isForeignPassage(PASSAGE)
    control._assistant_sources = []


def test_hint_says_return_will_translate(quick_env):
    editor = quick_env.root.findChild(QQuickItem, "draftEditor")
    editor.setProperty("text", PASSAGE)
    QTest.qWait(30)
    assert quick_env.root.property("composerKeyHints").toVariant() == [{"key": "↵", "label": "dịch"}]


class RecordingTranslator:
    def __init__(self):
        self.calls = []

    def translate(self, text, source="auto", target="vi"):
        self.calls.append((text, source, target))
        back = target == "en"
        return {"text": "Back to English." if back else "Bản dịch tiếng Việt.",
                "source_language": "vi" if back else "en", "provider": "offline_argos",
                "glossary_terms": 2, "line_joins": 0, "status": "complete", "warnings": []}


def _named(root, name):
    return root.findChild(QQuickItem, name)


def test_translation_card_shows_direction_method_and_a_source_sheet(quick_env):
    control, root = quick_env.controller, quick_env.root
    control._translator = RecordingTranslator()
    press_return(quick_env, PASSAGE)
    wait_for(lambda: control.snapshot["view"] == "answer")
    QTest.qWait(50)

    assert _named(root, "translationDirection").property("text") == "Tiếng Anh → Tiếng Việt"
    assert _named(root, "translationMethod").property("text") == "Dịch trên máy · giữ 2 thuật ngữ"
    assert _named(root, "translationBar").property("visible")
    assert not _named(root, "answerQuestionCard").property("visible")
    assert not _named(root, "copyCitation").property("visible")

    sheet = _named(root, "translationSourceSheet")
    assert not sheet.property("visible")
    toggle = _named(root, "translationSourceToggle")
    QTest.mouseClick(quick_env.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     toggle.mapToScene(QPointF(toggle.width() / 2, toggle.height() / 2)).toPoint())
    QTest.qWait(20)
    assert sheet.property("visible")
    assert _named(root, "translationSourceText").property("text") == PASSAGE


def test_flip_translates_the_translation_back_the_other_way(quick_env):
    control = quick_env.controller
    control._translator = RecordingTranslator()
    press_return(quick_env, PASSAGE)
    wait_for(lambda: control.snapshot["view"] == "answer")

    control.flipTranslation()
    wait_for(lambda: (control.snapshot["translation"] or {}).get("target") == "en")
    assert control._translator.calls[-1] == ("Bản dịch tiếng Việt.", "vi", "en")
    card = control.snapshot["translation"]
    assert card["direction"] == "Tiếng Việt → Tiếng Anh"
    assert card["sourceText"] == "Bản dịch tiếng Việt."
    assert card["text"] == "Back to English."


def test_a_later_answer_retires_the_translation_card(quick_env):
    control = quick_env.controller
    control._translator = RecordingTranslator()
    press_return(quick_env, PASSAGE)
    wait_for(lambda: control.snapshot["translation"] is not None)

    control._last_assistant_answer = "Một câu trả lời khác."
    assert control.snapshot["translation"] is None
    control.flipTranslation()
    assert len(control._translator.calls) == 1


def test_method_line_only_states_what_the_result_reports():
    from rat.ui.translation_card import method_line

    assert method_line({}) == ""
    assert method_line({"provider": "google_gtx, mymemory"}) == "Dịch qua Google · Dịch qua MyMemory"
    assert method_line({"provider": "offline_argos", "line_joins": 3}) == "Dịch trên máy · nối 3 dòng bị ngắt"
    assert method_line({"provider": "same_language", "target_lang": "vi"}) == "Đoạn này đã cùng ngôn ngữ, Chuột giữ nguyên"
    partial = method_line({"provider": "deepl", "status": "partial",
                           "warnings": ["Có thay đổi ở chữ số; hãy đối chiếu nguyên văn."]})
    assert partial == "Dịch qua DeepL · còn đoạn chưa dịch được · Có thay đổi ở chữ số; hãy đối chiếu nguyên văn."


SENTENCE = "We evaluated the model on three public benchmarks."


@pytest.fixture
def fake_language(monkeypatch):
    # Real detection needs macOS. These cover the rule; its measured table is in the docstring.
    def detect(text):
        return "vi" if "ộ" in text else ("id" if "bai tap" in text else "en")
    monkeypatch.setattr("rat.engine.snippet_translation.detect_language", detect)


@pytest.mark.parametrize("text, asks", [
    (SENTENCE, True),
    ("This paper proposes a new method for routing vehicles", True),
    ("vehicle routing problem with time windows", False),
    ("final report draft version 3 for review", False),
    ("AI ethics report", False),
    ("bai tap giai tich tuan 12 cua nhom toi nam nay", False),
    ("tìm hợp đồng thuê nhà của tôi.", False),
    ("find my thesis draft from last week.", False),
    ("open the budget spreadsheet right now.", False),
    ("translate this short sentence for me.", False),
    ("what is binary search and why use it.", False),
    ("Does this model work on three public benchmarks?", False),
    ("budget report for the third quarter.pdf", False),
    (PASSAGE, False),
    ("", False),
])
def test_when_a_sentence_offers_find_or_translate(fake_language, text, asks):
    assert offers_find_or_translate(text) is asks


def _choice_visible(root):
    return _named(root, "intentChoiceBar").property("visible")


def test_enter_asks_first_then_enter_translates(quick_env, fake_language):
    control, root = quick_env.controller, quick_env.root
    control._translator = RecordingTranslator()
    editor = press_return(quick_env, SENTENCE)
    QTest.qWait(30)
    assert _choice_visible(root)
    assert control._translator.calls == []
    assert quick_env.backend.run_calls == []

    QTest.keyClick(quick_env.view, Qt.Key.Key_Return)
    wait_for(lambda: control.snapshot["translation"] is not None)
    assert control._translator.calls[0][0] == SENTENCE
    assert editor.property("text") == ""
    assert not _choice_visible(root)


def test_tab_chooses_find_and_keeps_the_draft(quick_env, fake_language):
    control, root = quick_env.controller, quick_env.root
    control._translator = RecordingTranslator()
    editor = press_return(quick_env, SENTENCE)
    QTest.qWait(30)
    QTest.keyClick(quick_env.view, Qt.Key.Key_Tab)
    QTest.qWait(30)
    assert not _choice_visible(root)
    assert control._translator.calls == []
    assert editor.property("text") == SENTENCE
    assert control.snapshot["view"] == "finder" or "không tìm ra" in control.snapshot["finderFeedback"]


def test_esc_or_editing_retires_the_question(quick_env, fake_language):
    root = quick_env.root
    editor = press_return(quick_env, SENTENCE)
    QTest.qWait(30)
    assert _choice_visible(root)
    QTest.keyClick(quick_env.view, Qt.Key.Key_Escape)
    QTest.qWait(30)
    assert not _choice_visible(root)
    assert editor.property("text") == SENTENCE

    press_return(quick_env, SENTENCE)
    QTest.qWait(30)
    assert _choice_visible(root)
    editor.setProperty("text", SENTENCE + " Also")
    QTest.qWait(30)
    assert not _choice_visible(root)


def test_a_search_is_not_asked_about(quick_env, fake_language):
    press_return(quick_env, "vehicle routing problem with time windows")
    QTest.qWait(30)
    assert not _choice_visible(quick_env.root)


def test_source_sheet_pulls_out_by_dragging(quick_env):
    control, root = quick_env.controller, quick_env.root
    control._translator = RecordingTranslator()
    press_return(quick_env, PASSAGE)
    wait_for(lambda: control.snapshot["translation"] is not None)
    QTest.qWait(50)
    toggle = _named(root, "translationSourceToggle")
    start = toggle.mapToScene(QPointF(toggle.width() / 2, toggle.height() / 2)).toPoint()
    none = Qt.KeyboardModifier.NoModifier

    QTest.mousePress(quick_env.view, Qt.MouseButton.LeftButton, none, start)
    for step in range(1, 7):
        QTest.mouseMove(quick_env.view, start + QPoint(0, step * 8))
        QTest.qWait(10)
    QTest.mouseRelease(quick_env.view, Qt.MouseButton.LeftButton, none, start + QPoint(0, 48))
    QTest.qWait(30)
    assert root.property("translationSourceOpen") is True


def _status_text(root):
    return _named(root, "composerDropStatus").property("text")


def _quicklook_env(monkeypatch, selection, trusted=True):
    monkeypatch.setattr("rat.os.permissions.is_accessibility_trusted", lambda: trusted)
    monkeypatch.setattr("rat.os.selected_text.read_selected_text", selection)


def test_shortcut_answers_before_the_selection_is_read(quick_env, monkeypatch):
    control, root = quick_env.controller, quick_env.root
    control._translator = RecordingTranslator()
    release = threading.Event()

    def slow_selection():
        release.wait(3)
        return "Some selected words"
    _quicklook_env(monkeypatch, slow_selection)

    control.quickLookSelection()
    # Nothing has been read yet, and the answer is already on the desk.
    QTest.qWait(30)
    assert not control._translator.calls
    assert _status_text(root) == "Chuột đang lấy đoạn bạn bôi đen…"

    release.set()
    wait_for(lambda: control.snapshot["translation"] is not None)
    assert control._translator.calls[0][0] == "Some selected words"
    wait_for(lambda: control.snapshot["shortcutAck"] == "")
    assert control._shortcut_ack == ""


def test_shortcut_while_busy_says_so_and_does_not_start_again(quick_env, monkeypatch):
    control, root = quick_env.controller, quick_env.root
    control._translator = RecordingTranslator()
    _quicklook_env(monkeypatch, lambda: "Some selected words")
    control._translating = True
    control.quickLookSelection()
    QTest.qWait(30)
    assert control._translator.calls == []
    assert _status_text(root) == "Chuột đang bận việc trước. Xong rồi bấm lại nhé."
    assert control._shortcut_ack_timer.isActive()
    control._shortcut_ack_timer.timeout.emit()
    assert control.snapshot["shortcutAck"] == ""
    control._translating = False


@pytest.mark.parametrize("trusted, message", [
    (True, "Chuột không thấy đoạn bôi đen. Bôi đen hoặc ⌘C rồi bấm lại."),
    (False, "Chưa có quyền Trợ năng: ⌘C đoạn cần dịch rồi bấm lại."),
])
def test_shortcut_with_nothing_to_translate_says_what_to_do(quick_env, monkeypatch, trusted, message):
    control, root = quick_env.controller, quick_env.root
    _quicklook_env(monkeypatch, lambda: "", trusted)
    monkeypatch.setattr(control, "_get_clipboard_change_count", lambda: -1)
    control.quickLookSelection()
    wait_for(lambda: control.snapshot["shortcutAck"] == message)
    QTest.qWait(30)
    assert _status_text(root) == message
    assert control._shortcut_ack_timer.isActive()


def test_shortcut_translation_failure_is_shown_where_the_ack_was(quick_env, monkeypatch):
    control = quick_env.controller
    control._translator = FakeTranslator(OSError("model missing"))
    _quicklook_env(monkeypatch, lambda: "Some selected words")
    control.quickLookSelection()
    wait_for(lambda: control.snapshot["shortcutAck"] == "Chuột chưa dịch được: model missing")
    assert control._shortcut_ack_timer.isActive()


def _finish_run(control):
    control._warn_once_if_model_cannot_read_files()


def test_small_model_warning_shows_once(quick_env, monkeypatch):
    from rat.config import config
    from rat.engine.slm import slm_engine

    control = quick_env.controller
    monkeypatch.setattr(control.assistant_runtime, "model_client", None)
    monkeypatch.setattr(config, "assistant_model", "")
    monkeypatch.setattr(slm_engine, "list_installed_models", lambda: ["qwen2.5:1.5b"])

    _finish_run(control)
    wait_for(lambda: "ollama pull qwen3:4b-instruct" in control.snapshot["shortcutAck"])
    assert quick_env.root.property("ratOut")

    control._set_shortcut_ack("", 0)
    _finish_run(control)
    QTest.qWait(80)
    assert control.snapshot["shortcutAck"] == ""


def test_blocked_action_is_told_to_the_user(quick_env):
    from rat.engine.assistant_runtime import AgentResponse

    control, root = quick_env.controller, quick_env.root

    def run(query, **context):
        return AgentResponse("Tiền cọc là 7 triệu.", [], 0, 0, 12, telemetry_breakdown={
            "blocked_actions": [{"tool": "open_application", "label": "mở ứng dụng"}]})
    control.assistant_runtime.run = run
    press_return(quick_env, "tiền cọc là bao nhiêu?")
    wait_for(lambda: control.snapshot["shortcutAck"])
    assert control.snapshot["answerText"] == "Tiền cọc là 7 triệu."
    assert "Chuột đã chặn: mở ứng dụng" in control.snapshot["shortcutAck"]
    assert root.property("ratOut")
    assert "Đã chặn: open_application" in control.snapshot["events"]
