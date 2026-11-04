"""A long foreign passage in the composer is translated without calling a model."""
from PyQt6.QtCore import Qt
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtTest import QTest

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
    assert quick_env.backend.run_calls == [] and quick_env.backend.embed_calls == []


def test_failed_translation_keeps_the_draft_and_can_be_retried(quick_env):
    control = quick_env.controller
    control._translator = FakeTranslator(OSError("model missing"))
    editor = press_return(quick_env, PASSAGE)

    wait_for(lambda: "Dịch thất bại" in (control.snapshot["status"] or ""))
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
