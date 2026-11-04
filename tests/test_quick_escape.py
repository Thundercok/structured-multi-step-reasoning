"""Esc goes back exactly one step from every screen and keeps the draft."""
from PyQt6.QtCore import Qt
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtTest import QTest

from rat.ui.quick_app import create_quick_desk
from tests.test_quick_unified_flow import app, quick_env, wait_for  # noqa: F401

DRAFT = "chữ đang gõ dở"
PAGE = {"page": 1, "page_count": 1, "filename": "x.pdf", "content": "nội dung"}


def press_escape(env):
    QTest.keyClick(env.view, Qt.Key.Key_Escape)
    QTest.qWait(30)


def type_draft(env, text=DRAFT):
    editor = env.root.findChild(QQuickItem, "draftEditor")
    editor.setProperty("text", text)
    editor.forceActiveFocus()
    QTest.qWait(20)
    return editor


def show_page(control, returns_to):
    control._last_assistant_answer = "câu trả lời"
    control._page = dict(PAGE)
    control._page_return_view = returns_to
    control._view = "page"
    control._expanded = True
    control.changed.emit()
    QTest.qWait(30)


def test_page_goes_back_to_answer_then_folds_and_keeps_draft(quick_env):
    control = quick_env.controller
    editor = type_draft(quick_env)
    show_page(control, "answer")

    press_escape(quick_env)
    assert control.snapshot["view"] == "answer"
    assert control.snapshot["expanded"]

    press_escape(quick_env)
    assert control.snapshot["view"] == "answer"
    assert not control.snapshot["expanded"]
    assert editor.property("text") == DRAFT


def test_page_goes_back_to_search_results(quick_env):
    control = quick_env.controller
    control._search = {"query": "x", "matched_pages": 1, "items": [], "page_count": 1,
                       "searched_range": (1, 1), "textless_pages": [], "next_page": 0}
    show_page(control, "search")

    press_escape(quick_env)
    assert control.snapshot["view"] == "search"
    assert control.snapshot["expanded"]


def test_expanded_reading_desk_closes_instead_of_folding(quick_env):
    control = quick_env.controller
    control.setExpanded(True)
    control.openReadingDesk()
    QTest.qWait(30)
    assert control.snapshot["view"] == "reading"

    press_escape(quick_env)
    assert control.snapshot["view"] != "reading"
    assert control.snapshot["expanded"]


def test_apps_view_restores_the_draft(quick_env):
    control = quick_env.controller
    editor = type_draft(quick_env)
    control.openAppsView(DRAFT)
    editor.setProperty("text", "")
    QTest.qWait(30)
    assert control.snapshot["view"] == "apps"

    press_escape(quick_env)
    assert control.snapshot["view"] != "apps"
    assert editor.property("text") == DRAFT


def test_inline_pdf_search_closes_before_the_page_changes(quick_env):
    control = quick_env.controller
    show_page(control, "answer")
    quick_env.root.setProperty("inlineFindOpen", True)
    QTest.qWait(30)

    press_escape(quick_env)
    assert not quick_env.root.property("inlineFindOpen")
    assert control.snapshot["view"] == "page"


def test_escape_works_when_focus_is_not_on_the_composer(quick_env):
    control = quick_env.controller
    show_page(control, "answer")
    quick_env.root.forceActiveFocus()
    QTest.qWait(30)

    press_escape(quick_env)
    assert control.snapshot["view"] == "answer"


def test_escape_at_rest_hides_a_resident_desk_and_keeps_the_draft(app):
    view, control = create_quick_desk(reduced_motion=True, quit_on_close=False)
    try:
        view.show()
        QTest.qWait(40)
        editor = view.rootObject().findChild(QQuickItem, "draftEditor")
        editor.setProperty("text", DRAFT)
        editor.forceActiveFocus()
        QTest.qWait(20)
        control.dismissFinder()
        QTest.qWait(20)

        QTest.keyClick(view, Qt.Key.Key_Escape)
        QTest.qWait(30)
        assert not view.isVisible()
        assert editor.property("text") == DRAFT

        view.show()
        QTest.qWait(30)
        assert view.isVisible() and editor.property("text") == DRAFT
    finally:
        control.close()
        view.close()
        view.deleteLater()


def test_escape_at_rest_does_nothing_when_closing_would_quit(quick_env):
    closed = []
    quick_env.root.closeRequested.connect(lambda: closed.append(True))
    editor = type_draft(quick_env)
    quick_env.controller.dismissFinder()
    QTest.qWait(20)

    press_escape(quick_env)
    assert closed == []
    assert quick_env.view.isVisible() and editor.property("text") == DRAFT


def test_escape_on_a_folded_page_stays_folded(quick_env):
    control = quick_env.controller
    show_page(control, "answer")
    control.setExpanded(False)
    type_draft(quick_env)

    press_escape(quick_env)
    assert control.snapshot["view"] == "page"
    assert not control.snapshot["expanded"]
