import sys
import os
import shutil
from pathlib import Path
from PyQt6.QtCore import QPoint, QPointF, QUrl, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PIL import Image
import numpy as np

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window

os.environ["QT_QUICK_BACKEND"] = "software"

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
controller = QuickPDFController(auto_init_finder=False)
controller.ready()

view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.setInitialProperties({"liveController": controller, "reduceMotion": True})
view.setSource(QUrl.fromLocalFile(str(Path("rat/ui/quick/PDFDesk.qml").resolve())))
root = view.rootObject()
view.resize(520, round(root.property("preferredWindowHeight")))
timer = bind_desk_window(view)
view.show()
QTest.qWait(300)

def wait_for_idle(timeout_ms=10000):
    elapsed = 0
    while elapsed < timeout_ms:
        QTest.qWait(50)
        elapsed += 50
        if not controller.snapshot.get("busy"):
            return
    raise TimeoutError(f"Timed out waiting for controller idle, snapshot={controller.snapshot}")

def find_item(root, name):
    item = root.findChild(QQuickItem, name)
    if item is not None:
        return item
    pending = list(root.childItems())
    while pending:
        candidate = pending.pop()
        if candidate.objectName() == name:
            return candidate
        pending.extend(candidate.childItems())
    return None

def click_item(item):
    assert item is not None and item.isVisible(), f"Item {item} must be visible to click"
    scene_pos = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    pt = scene_pos.toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
    QTest.qWait(150)

# 1. Type draft in composer
editor = root.findChild(QQuickItem, "draftEditor")
assert editor is not None, "draftEditor must exist"
initial_draft = "Câu hỏi đang soạn dở trong ô chat: chi phí routing LLM"
editor.setProperty("text", initial_draft)
assert editor.property("text") == initial_draft

# 2. Select authentic PDF fixture
pdf_path = "work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf"
assert Path(pdf_path).exists(), f"PDF path {pdf_path} must exist"
controller.openPdfDocument(pdf_path)
wait_for_idle()

# 3. Perform search for keyword "routing"
controller.search("routing")
wait_for_idle()
QTest.qWait(300)
items = controller.snapshot.get("items") or []
assert len(items) > 0, f"Expected search hits for 'routing', got: {controller.snapshot}"
print(f"Found {len(items)} search hits for 'routing': {[h['page'] for h in items]}")

if not root.property("expanded"):
    root.setProperty("expanded", True)
    controller.setExpanded(True)
    QTest.qWait(300)

# 4. Open first search hit
hit_first = items[0]
target_page = hit_first["page"]
print(f"Opening search hit on page {target_page}")

view.resize(view.width(), round(root.property("preferredWindowHeight")))
QTest.qWait(200)

read_btn = find_item(root, f"readHit_{target_page}")
assert read_btn is not None, f"readHit_{target_page} must exist"
click_item(read_btn)
wait_for_idle()

# 5. Verify snapshot and single source flow properties
snap = controller.snapshot
assert snap.get("view") == "page", f"Expected view == 'page', got {snap.get('view')}"
assert snap.get("pageNumber") == target_page, f"Expected pageNumber == {target_page}, got {snap.get('pageNumber')}"
assert snap.get("hasMatchedSnippet") is True, "hasMatchedSnippet must be True"
assert snap.get("matchedQuery") == "routing", f"Expected matchedQuery == 'routing', got {snap.get('matchedQuery')}"
assert snap.get("sourceKind") == "search_hit", f"Expected sourceKind == 'search_hit', got {snap.get('sourceKind')}"

# 6. Verify Title and Metadata presentation
title_item = find_item(root, "pageSourceTitle")
assert title_item is not None, "pageSourceTitle must exist"
title_text = title_item.property("text")
print(f"pageSourceTitle text: {title_text!r}")
assert title_text == f"Nguồn · Trang {target_page}", f"Expected 'Nguồn · Trang {target_page}', got {title_text!r}"

meta_item = find_item(root, "pageMetadataLabel")
assert meta_item is not None, "pageMetadataLabel must exist"
meta_text = meta_item.property("text")
print(f"pageMetadataLabel text: {meta_text!r}")
assert meta_text == "arxiv_2506.22716_original.pdf", f"Expected filename in meta, got {meta_text!r}"

# 7. Assert switcher is completely removed, header only has backToSearch/copyCitation/liveFoldButton, and only ONE openOriginalExternal exists next to metadata
assert find_item(root, "readerModeToggle") is None, "readerModeToggle switcher must be removed"
open_external_btn = find_item(root, "openOriginalExternal")
assert open_external_btn is not None and open_external_btn.isVisible(), "openOriginalExternal button must be visible"

# Verify header cleanliness in this search hit flow: prev, next, pagePicker, readPage, and header openOriginal are NOT present
page_picker = find_item(root, "pagePicker")
assert page_picker is None or not page_picker.isVisible(), "pagePicker must be hidden in search hit source flow"
prev_btn = find_item(root, "prevPage")
assert prev_btn is None or not prev_btn.isVisible(), "prevPage must be hidden in search hit source flow"
next_btn = find_item(root, "nextPage")
assert next_btn is None or not next_btn.isVisible(), "nextPage must be hidden in search hit source flow"
read_btn_jump = find_item(root, "readPage")
assert read_btn_jump is None or not read_btn_jump.isVisible(), "readPage must be hidden in search hit source flow"
assert find_item(root, "openOriginal") is None, "Duplicate openOriginal icon must not exist on header"

back_btn_check = find_item(root, "backToSearch")
assert back_btn_check is not None and back_btn_check.isVisible(), "backToSearch must be visible on header"
assert back_btn_check.property("text") in ("Quay lại kết quả", "Kết quả"), f"Unexpected back button text: {back_btn_check.property('text')!r}"
fold_btn_check = find_item(root, "liveFoldButton")
assert fold_btn_check is not None and fold_btn_check.isVisible(), "liveFoldButton must be visible on header"

# 8. Verify matched excerpt element and keyword highlight
matched_wrapper = find_item(root, "matchedExcerptWrapper")
assert matched_wrapper is not None and matched_wrapper.isVisible(), "matchedExcerptWrapper must be visible"

matched_text = find_item(root, "matchedExcerptText")
assert matched_text is not None and matched_text.isVisible(), "matchedExcerptText must be visible"
html_content = matched_text.property("text")
assert "routing" in html_content.lower(), "Excerpt must contain search keyword"
assert "background-color" in html_content, "Excerpt must have highlighted search keyword"

# 9. Verify draft text is untouched
assert editor.property("text") == initial_draft, "Draft in composer was mutated!"

# 10. Verify copy button text and genuine clipboard confirmation
copy_btn = find_item(root, "copyCitation")
assert copy_btn is not None and copy_btn.isVisible(), "copyCitation must be visible"
assert copy_btn.property("text") == "Chép đoạn", f"Expected 'Chép đoạn', got {copy_btn.property('text')!r}"

copied_citations = []
confirmed_citations = []
controller.copyReady.connect(copied_citations.append)
controller.copyConfirmed.connect(confirmed_citations.append)

click_item(copy_btn)
QTest.qWait(100)
assert len(copied_citations) == 1, "Expected 1 citation from copyReady"
assert len(confirmed_citations) == 1, "Expected 1 confirmation from copyConfirmed"
# Assert REAL OS clipboard
actual_clipboard = app.clipboard().text()
print(f"Actual verified OS clipboard:\n{actual_clipboard}")
assert actual_clipboard == copied_citations[0], "Clipboard content does not match copied citation!"
assert "arxiv_2506.22716_original.pdf" in actual_clipboard
assert f"trang PDF {target_page}" in actual_clipboard
assert copy_btn.property("text") == "Đã chép", f"Expected 'Đã chép', got {copy_btn.property('text')!r}"

# 11. Partial text selection copy
displayed_snippet = snap.get("matchedSnippet") or ""
if "routing" in displayed_snippet.lower():
    sel_start = displayed_snippet.lower().index("routing")
    matched_text.select(sel_start, sel_start + len("routing"))
    sel_text = matched_text.property("selectedText").strip()
    assert sel_text != ""
    click_item(copy_btn)
    QTest.qWait(100)
    assert len(copied_citations) == 2
    assert app.clipboard().text() == copied_citations[1]
    assert sel_text in app.clipboard().text()
    print("Partial selection copy passed:", sel_text)

# 12. Desktop Scroll from Top to Bottom of 'routing' snippet at 520px
os.makedirs("work/turn4_evidence", exist_ok=True)
artifact_dir = Path("/Users/thundercock2/.gemini/antigravity/brain/c521fb94-cdbc-4b76-8354-89e731c844c7")

scroll = find_item(root, "resultScroll")
assert scroll is not None, "resultScroll must exist"
content_item = scroll.property("contentItem")
assert content_item is not None, "contentItem must exist"

# Capture top of snippet at 520px
top_img_path = "work/turn4_evidence/turn4_matched_excerpt_520px_top.png"
view.grabWindow().save(top_img_path)
view.grabWindow().save("work/turn4_evidence/turn4_matched_excerpt_520px.png")
shutil.copy2(top_img_path, str(artifact_dir / "turn4_matched_excerpt_520px_top.png"))
shutil.copy2(top_img_path, str(artifact_dir / "turn4_matched_excerpt_520px.png"))
print(f"Captured 520px top image: {top_img_path}")

# Verify ScrollBar is visible and distinct (width=6) when content exceeds
v_bar = find_item(root, "resultVerticalScroll")
assert v_bar is not None and v_bar.isVisible(), "resultVerticalScroll must be visible when content overflows"
assert v_bar.width() == 6, f"ScrollBar width must be 6px for visibility, got {v_bar.width()}"
thumb = v_bar.property("contentItem")
assert thumb is not None and thumb.isVisible(), "ScrollBar thumb must be visible"

# Perform genuine desktop mouse drag on scrollbar thumb to scroll to bottom
thumb_scene = thumb.mapToScene(QPointF(thumb.width() / 2, thumb.height() / 2)).toPoint()
QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, thumb_scene)
QTest.qWait(50)
for step in range(10, 180, 20):
    curr_pt = QPoint(thumb_scene.x(), thumb_scene.y() + step)
    QTest.mouseMove(view, curr_pt)
    QTest.qWait(25)
target_drag_pt = QPoint(thumb_scene.x(), thumb_scene.y() + 180)
QTest.mouseMove(view, target_drag_pt)
QTest.qWait(50)
QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target_drag_pt)
QTest.qWait(100)

scrolled_y = content_item.property("contentY")
print(f"Scrolled to bottom via desktop mouse drag: contentY = {scrolled_y}")
assert scrolled_y >= 150.0, f"Expected contentY >= 150, got {scrolled_y}"

# Verify no occlusion: scroll bottom is strictly above composer top
composer = find_item(root, "composer")
composer_top = composer.mapToScene(QPointF(0, 0)).y()
scroll_bottom = scroll.mapToScene(QPointF(0, scroll.height())).y()
print(f"scroll_bottom: {scroll_bottom}, composer_top: {composer_top}, clearance: {composer_top - scroll_bottom}px")
assert scroll_bottom <= composer_top, "scroll viewport must not extend into composer"
assert composer_top - scroll_bottom >= 10, "composer must not occlude or block scroll viewport"

# Verify reading and selecting the last line
last_line_marker = "Model Cascade"
assert last_line_marker in displayed_snippet, "Last line marker must be in displayed snippet"
last_line_idx = displayed_snippet.index(last_line_marker)
matched_text.select(last_line_idx, last_line_idx + len(last_line_marker))
selected_last = matched_text.property("selectedText").strip()
print(f"Selected last line text: {selected_last!r}")
assert selected_last == last_line_marker, f"Expected {last_line_marker!r}, got {selected_last!r}"

click_item(copy_btn)
QTest.qWait(100)
assert last_line_marker in app.clipboard().text(), "OS clipboard must contain selected text from last line"
print(f"Verified OS clipboard has last line: {app.clipboard().text()[:40]}...")

# Capture bottom of snippet at 520px
bottom_img_path = "work/turn4_evidence/turn4_matched_excerpt_520px_bottom.png"
view.grabWindow().save(bottom_img_path)
shutil.copy2(bottom_img_path, str(artifact_dir / "turn4_matched_excerpt_520px_bottom.png"))
print(f"Captured 520px bottom image: {bottom_img_path}")

# 13. Check fallback state: read a page that has NO matched snippet (page 25)
controller.readPage(25)
wait_for_idle()
assert controller.snapshot.get("pageNumber") == 25
assert controller.snapshot.get("hasMatchedSnippet") is False
fallback_btn = find_item(root, "openOriginalFallback")
assert fallback_btn is not None and fallback_btn.isVisible(), "openOriginalFallback must be visible on page with no snippet"
# In fallback state without overflow, scrollbar must not be shown
assert not v_bar.isVisible(), "ScrollBar must hide when content does not overflow"
print("Page 25 fallback state and ScrollBar hiding verified successfully.")

# Return to target page
controller.readPage(target_page)
wait_for_idle()

# 14. Test openOriginal does not mutate draft or view
opened_urls = []
controller._open_url = lambda url: opened_urls.append(url) or True
assert controller.openOriginal()
assert len(opened_urls) == 1
assert "arxiv_2506.22716_original.pdf" in opened_urls[0].toString()
assert editor.property("text") == initial_draft, "Draft was mutated after openOriginal!"

# 15. Test backToSearch returns cleanly to search hits
back_btn = find_item(root, "backToSearch")
assert back_btn is not None and back_btn.isVisible(), "backToSearch must be visible"
click_item(back_btn)
wait_for_idle()
assert controller.snapshot.get("view") == "search", "Expected to return to search view"
assert editor.property("text") == initial_draft, "Draft was mutated after backToSearch!"
assert controller.snapshot.get("searchQuery") == "routing", "Search query was lost after backToSearch!"
print("backToSearch verified successfully.")

# Re-enter target page hit
read_btn = find_item(root, f"readHit_{target_page}")
click_item(read_btn)
wait_for_idle()

# 16. Test follow-up composer UX while reading source
doc_chip = find_item(root, "documentMenu")
assert doc_chip is not None, "documentMenu chip must exist"
doc_chip_text = doc_chip.property("text")
print(f"Document chip text: {doc_chip_text!r}")
assert doc_chip_text == "arxiv_2506.22716_original.pdf", f"Expected clean filename without page restriction, got {doc_chip_text!r}"

# 16. Composer Interaction: Focus, Placeholder, and Text Editing Primitives
# Focus composer while reading source -> verify source does NOT close, finder does NOT open
editor_pos = editor.mapToScene(QPointF(editor.width() / 2, editor.height() / 2)).toPoint()
QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, editor_pos)
QTest.qWait(50)
assert editor.hasActiveFocus(), "editor must receive focus on click"
assert controller.snapshot.get("view") == "page", "Focusing composer must not close page view"
assert matched_wrapper.isVisible(), "Source excerpt must remain visible when composer is focused"
finder_section = find_item(root, "finderSection")
assert finder_section is None or not finder_section.isVisible(), "Focusing composer while reading source must not open Finder"

# Test placeholder when draft is empty
editor.setProperty("text", "")
QTest.qWait(50)
assert editor.property("text") == "", "Draft must remain empty"
placeholder_text = editor.property("placeholderText")
print(f"Empty draft placeholder: {placeholder_text!r}")
assert placeholder_text == "Hỏi tiếp về tài liệu này…", f"Expected follow-up placeholder, got {placeholder_text!r}"

# Test Qt Quick text editing primitives (paste, undo, redo)
test_clipboard_text = "Chi phí triển khai LLM"
app.clipboard().setText(test_clipboard_text)
editor.paste()
QTest.qWait(50)
print(f"Text after editor.paste(): {editor.property('text')!r}")
assert editor.property("text") == test_clipboard_text, f"Expected {test_clipboard_text!r}, got {editor.property('text')!r}"
assert controller.snapshot.get("view") == "page", "Pasting must not dismiss source page"

editor.undo()
QTest.qWait(50)
print(f"Text after editor.undo(): {editor.property('text')!r}")
assert editor.property("text") == "", "Undo must revert pasted text"

editor.redo()
QTest.qWait(50)
print(f"Text after editor.redo(): {editor.property('text')!r}")
assert editor.property("text") == test_clipboard_text, "Redo must restore pasted text"

# Ghi chú kỹ thuật: setProperty chỉ dùng để kiểm tra data binding và tính năng lưu giữ bản nháp
# (draft retention contract) qua các trạng thái điều hướng, KHÔNG PHẢI là thao tác gõ phím bằng bộ gõ hay dán bằng Cmd+V.
pasted_query = "Tìm chi phí triển khai LLM - Model Cascade"
editor.setProperty("text", pasted_query)
QTest.qWait(50)
assert editor.property("text") == pasted_query

# 17. Test draft preservation across backToSearch, re-open hit, and min/full
back_btn = find_item(root, "backToSearch")
click_item(back_btn)
wait_for_idle()
assert controller.snapshot.get("view") == "search"
assert editor.property("text") == pasted_query, "Draft was mutated after backToSearch!"

read_btn = find_item(root, f"readHit_{target_page}")
click_item(read_btn)
wait_for_idle()
assert controller.snapshot.get("view") == "page"
assert editor.property("text") == pasted_query, "Draft was mutated after re-opening search hit!"

click_item(find_item(root, "liveFoldButton"))
assert not root.property("expanded"), "Expected workbench folded in min mode"
assert editor.property("text") == pasted_query, "Draft was mutated after folding to min mode!"
notice_card = find_item(root, "notice")
assert notice_card is not None and notice_card.isVisible(), "notice card must be visible in min mode"
click_item(notice_card)
assert root.property("expanded"), "Expected workbench expanded in full mode"
assert editor.property("text") == pasted_query, "Draft was mutated after expanding to full mode!"
print("Follow-up composer draft preserved 100% across all navigation states.")

# Zero model requests assertion
assert controller._request is None, "Must not dispatch requests to model"
assert not controller.snapshot.get("busy"), "Controller must remain idle"
assert controller._current_worker is None, "No worker should be executing"
print("Zero model requests strictly verified (0 calls).")

# 18. Capture screenshots at 520px and 700px production dimensions
captures = {
    "top_520": top_img_path,
    "bottom_520": bottom_img_path,
}

view.resize(700, round(root.property("preferredWindowHeight")))
QTest.qWait(350)
img_700_path = "work/turn4_evidence/turn4_matched_excerpt_700px.png"
ok = view.grabWindow().save(img_700_path)
assert ok, f"Failed to save {img_700_path}"
captures["matched_700"] = img_700_path
shutil.copy2(img_700_path, str(artifact_dir / "turn4_matched_excerpt_700px.png"))
print(f"Saved and copied to artifact: {img_700_path} (700px)")

# 17. Image quality and non-transparency verification
for name, p in captures.items():
    im = Image.open(p)
    arr = np.array(im)
    assert arr.shape[0] > 100 and arr.shape[1] > 100, f"Image {p} too small: {arr.shape}"
    assert arr.shape[2] == 4, f"Image {p} missing alpha: {arr.shape}"
    non_transparent = np.count_nonzero(arr[:, :, 3] > 10)
    total_px = arr.shape[0] * arr.shape[1]
    ratio = non_transparent / total_px
    print(f"Image {p}: size={im.size}, non-transparent ratio={ratio:.2%}")
    assert ratio > 0.40, f"Image {p} is too transparent: ratio={ratio:.2%}"

print("Giới hạn kiểm thử mở ngoài: controller._open_url được mock trong script để kiểm tra QUrl gửi đi. Điều này chứng minh URL file cục bộ chính xác đã được chuyển đến opener, nhưng chưa chứng minh tiến trình ứng dụng ngoài thực sự được kích hoạt trên desktop macOS, và không mở đúng trang vì hiện chỉ gửi file URL.")
print("Giới hạn kiểm thử nhập liệu: setProperty chỉ kiểm tra binding dữ liệu và lưu giữ bản nháp (draft retention contract) qua các trạng thái điều hướng, KHÔNG PHẢI là thao tác gõ phím hay dán bằng Cmd+V. Thao tác gõ tiếng Việt bằng bộ gõ hệ điều hành (macOS IME) và dán/undo/redo bằng phím tắt vật lý OS (Cmd+V, Cmd+Z, Cmd+Shift+Z) được ghi nhận là CHƯA XÁC NHẬN trên môi trường tự động (cần người dùng tương tác trực tiếp trên desktop).")
print("\n--- ALL BUILD 2026.10.24.16 VERIFICATIONS PASSED SUCCESSFULLY ---")
