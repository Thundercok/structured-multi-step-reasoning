"""A long foreign passage in the composer is translated without calling a model."""
from PyQt6.QtCore import QPointF, Qt
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
