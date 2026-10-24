import sys
import os
import shutil
from pathlib import Path
from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PIL import Image
import numpy as np

from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window

os.environ["QT_QUICK_BACKEND"] = "software"

app = QApplication.instance() or QApplication(sys.argv)
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

# 7. Assert switcher is completely removed, secondary action 'Mở PDF gốc' exists
assert find_item(root, "readerModeToggle") is None, "readerModeToggle switcher must be removed"
open_external_btn = find_item(root, "openOriginalExternal")
assert open_external_btn is not None and open_external_btn.isVisible(), "openOriginalExternal button must be visible"

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

# 12. Check fallback state: read a page that has NO matched snippet (page 25)
controller.readPage(25)
wait_for_idle()
assert controller.snapshot.get("pageNumber") == 25
assert controller.snapshot.get("hasMatchedSnippet") is False
fallback_btn = find_item(root, "openOriginalFallback")
assert fallback_btn is not None and fallback_btn.isVisible(), "openOriginalFallback must be visible on page with no snippet"
print("Page 25 fallback state verified successfully.")

# Return to target page for screenshots
controller.readPage(target_page)
wait_for_idle()

# 13. Test openOriginal does not mutate draft or view
opened_urls = []
controller._open_url = lambda url: opened_urls.append(url) or True
assert controller.openOriginal()
assert len(opened_urls) == 1
assert "arxiv_2506.22716_original.pdf" in opened_urls[0].toString()
assert editor.property("text") == initial_draft, "Draft was mutated after openOriginal!"

# 14. Test backToSearch returns cleanly to search hits
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

# 15. Test min/full mode transition
click_item(find_item(root, "liveFoldButton"))
assert not root.property("expanded"), "Expected workbench folded in min mode"
assert editor.property("text") == initial_draft, "Draft was mutated after folding!"
notice_card = find_item(root, "notice")
assert notice_card is not None and notice_card.isVisible(), "notice card must be visible in min mode"
click_item(notice_card)
assert root.property("expanded"), "Expected workbench expanded in full mode"
assert editor.property("text") == initial_draft, "Draft was mutated after expanding!"
print("Min/full mode transitions verified successfully.")

# 16. Capture screenshots at 520px and 700px production dimensions
os.makedirs("work/turn4_evidence", exist_ok=True)
artifact_dir = Path("/Users/thundercock2/.gemini/antigravity/brain/c521fb94-cdbc-4b76-8354-89e731c844c7")
captures = {}

for w in [520, 700]:
    view.resize(w, round(root.property("preferredWindowHeight")))
    QTest.qWait(350)
    img_path = f"work/turn4_evidence/turn4_matched_excerpt_{w}px.png"
    ok = view.grabWindow().save(img_path)
    assert ok, f"Failed to save {img_path}"
    captures[f"matched_{w}"] = img_path
    shutil.copy2(img_path, str(artifact_dir / f"turn4_matched_excerpt_{w}px.png"))
    print(f"Saved and copied to artifact: {img_path} ({w}px)")

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

print("\n--- ALL BUILD 2026.10.24.13 VERIFICATIONS PASSED SUCCESSFULLY ---")
