"""Live visual smoke with explicit user-supplied profile/cards, no model doubles.

Usage: python scripts/verify_reading_turn1.py --profile /absolute/profile.json
       --cards '4 pent, 8 cups, devil'
The native picker is not automated: profile selection uses the public import
slot; card entry, apply, folding and back navigation use actual Qt input events.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument('--profile', type=Path, required=True)
parser.add_argument('--cards', required=True)
parser.add_argument('--space', action='store_true')
parser.add_argument('--pdf', type=Path)
args = parser.parse_args()
OUT = ROOT / 'artifacts' / ('reading_input_smoke_' + time.strftime('%Y%m%d_%H%M%S') + '_' + str(os.getpid()))
OUT.mkdir(exist_ok=True, parents=True)
os.environ.setdefault('RAT_STATE_DIR', str(OUT / 'state'))
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtQuick import QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QGuiApplication
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window

app = QGuiApplication(sys.argv)
app.setFont(QFont('Helvetica Neue', 13))
clipboard_before = app.clipboard().text()
controller = QuickPDFController(auto_init_finder=False)
controller.ready()
view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setTitle('RAT · Workbench · ' + ('Build .24' if args.space else 'Bàn xem'))
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.setInitialProperties({'liveController': controller, 'reduceMotion': True, 'maxPaperHeight': 650})
view.setSource(QUrl.fromLocalFile(str(ROOT / 'rat/ui/quick/PDFDesk.qml')))
assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]
root = view.rootObject()
view.resize(700, 820)
timer = bind_desk_window(view)
view.show()
view.requestActivate()
QTest.qWait(250)
report = {'acceptance_scope': 'Input tools and unavailable-model handling only; not live model acceptance.',
          'model_requests': 0, 'profile_sha256': hashlib.sha256(args.profile.read_bytes()).hexdigest(),
          'profile_origin': 'Explicit local birth profile from user-provided birth inputs; recalculated by Swiss Ephemeris.',
          'cards_origin': 'Manually supplied cards; no random draw or canned interpretation.',
          'input_scope': 'Native Qt click/paste/key events; import via public slot, not native file picker acceptance.',
          'screenshots': []}


def find(name):
    pending = [root]
    while pending:
        item = pending.pop()
        if item.objectName() == name:
            return item
        pending.extend(item.childItems())
    raise AssertionError(name)


def click(name):
    item = find(name)
    assert item.isVisible(), name
    try:
        scroll = find('resultScroll').property('contentItem')
        scene_pos = item.mapToScene(QPointF(item.width()/2, item.height()/2))
        current_y = float(scroll.property('contentY'))
        new_y = max(0.0, current_y + (scene_pos.y() - view.height() / 2))
        scroll.setProperty('contentY', new_y)
        QTest.qWait(100)
    except Exception:
        pass
    QTest.qWait(150)
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    QTest.qWait(100)


def paste(name, text):
    click(name)
    QTest.keyClick(view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    app.clipboard().setText(text)
    QTest.keyClick(view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(80)


def capture(name):
    QTest.qWait(200)
    assert view.grabWindow().save(str(OUT / name))
    report['screenshots'].append(name)


try:
    paste('draftEditor', '/reading')
    QTest.keyClick(view, Qt.Key.Key_Return)
    QTest.qWait(200)
    assert controller.snapshot['view'] == 'reading'
    capture('reading_empty.png')
    assert controller.importReadingProfile(str(args.profile))
    QTest.qWait(250)
    deadline = time.perf_counter() + 30
    while not find('readingNatalWheel').property('wheelReady'):
        assert not find('readingNatalWheel').property('wheelFailed'), 'wheel image failed to load'
        assert time.perf_counter() < deadline, 'wheel image load timeout'
        QTest.qWait(50)
    paste('readingCardsEntry', args.cards)
    click('readingApplyCards')
    assert len(controller.snapshot['readingSession']['cards']) >= 3
    assert set(controller.snapshot['readingSession']['resultRefs']) == {'prepare_reading_spread', 'load_reading_profile'}
    report['reasoning_tools'] = list(controller.snapshot['readingSession']['resultRefs'])
    report['architecture_scope'] = 'Explicit user actions use shared agent dispatcher, validated tools, stored artifacts and execution events. Model planning/interpretation loop is not yet connected to this view.'
    assert find('readingCard_0').isVisible()
    paste('draftEditor', 'ban nhap phien xem dang giu')
    for width in (700, 520):
        view.resize(width, view.height())
        capture(f'reading_full_{width}.png')
    if args.space:
        base_width = view.width()
        session_before = controller.snapshot['readingSession']
        conversation_before = controller.conversation
        messages_before = controller.conversation.messages_with_turn_ids()
        artifact_ids_before = [(a.id, a.revision) for a in controller.assistant_runtime.artifact_store.list()]
        click('workspaceSizeButton')
        QTest.qWait(250)
        assert root.property('roomyActive') and view.width() > base_width
        assert view.screen().availableGeometry().contains(view.geometry()), str(view.geometry())
        assert find('readingSurfaceGrid').property('columns') == 2
        capture('workbench_expanded.png')
        report['expanded_geometry'] = [view.x(), view.y(), view.width(), view.height()]
        assert controller.snapshot['readingSession'] == session_before
        assert controller.conversation is conversation_before
        assert controller.conversation.messages_with_turn_ids() == messages_before
        assert artifact_ids_before == [(a.id, a.revision) for a in controller.assistant_runtime.artifact_store.list()]
        click('workspaceSizeButton')
        assert view.width() == base_width
        capture('workbench_restored.png')
        click('workspaceSizeButton')
        click('liveFoldButton')
        assert not root.property('roomyActive') and view.width() == base_width
        capture('workbench_folded.png')
        click('notice')
        assert root.property('roomyActive') and view.width() > base_width
        capture('workbench_reopened.png')
        click('workspaceSizeButton')
        assert view.width() == base_width
        assert find('draftEditor').property('text') == 'ban nhap phien xem dang giu'
        report['space_preserves_session_artifacts_draft'] = True
        report['conversation_scope'] = 'Conversation object and existing messages unchanged; no model conversation injected or generated.'
    scroll = find('resultScroll').property('contentItem')
    scroll.setProperty('contentY', max(0, scroll.property('contentHeight') - scroll.height()))
    capture('reading_cards_520.png')
    scroll.setProperty('contentY', 0)
    # Failed selection must not destroy the already calculated chart/cards.
    before = controller.snapshot['readingSession']
    assert not controller.importReadingProfile(str(ROOT / 'AGENTS.md'))
    after = controller.snapshot['readingSession']
    assert after['chart'] == before['chart'] and after['cards'] == before['cards']
    capture('reading_import_error.png')
    assert controller.importReadingProfile(str(args.profile))
    click('liveFoldButton')
    capture('reading_compact.png')
    assert find('draftEditor').property('text') == 'ban nhap phien xem dang giu'
    click('notice')
    QTest.qWait(200)
    click('backFromReading')
    assert find('draftEditor').property('text') == 'ban nhap phien xem dang giu'
    controller.openReadingDesk()
    assert controller.snapshot['readingSession']['cards'] == before['cards']
    assert find('draftEditor').property('text') == 'ban nhap phien xem dang giu'
    assert not controller.submit('Soạn bản luận cho trải bài')
    snap = controller.snapshot['readingSession']
    assert not snap['draft'] and not snap['cotSteps'] and not snap['grounds']
    assert 'model_unavailable' in snap['error']
    assert snap['cards'] == before['cards'] and snap['chart'] == before['chart']
    assert not controller.saveReadingDraft('Không có bản luận để lưu.')
    capture('reading_model_unavailable.png')

    report['reasoning_tools'] = list(snap['resultRefs'])
    report['architecture_scope'] = 'Shared dispatcher contracts for supplied inputs; interpretation Agent/model loop is not connected.'
    report['synthesis_status'] = 'model_unavailable'
    report['draft_created'] = False
    report['model_loop_connected'] = False
    report['live_model_acceptance'] = False
    report['draft_preserved'] = True
    report['invalid_import_preserves_session'] = True
    if args.pdf:
        controller.closeReadingDesk()
        controller.openPdfDocument(str(args.pdf))
        deadline = time.perf_counter() + 15
        while controller.snapshot['busy']:
            assert time.perf_counter() < deadline, 'PDF open timeout'
            QTest.qWait(25)
        assert controller.snapshot['fileName'] == args.pdf.name
        selected_before = controller.snapshot['activeContext']
        page_before = controller.snapshot['pageNumber']
        draft_before = find('draftEditor').property('text')
        base_width = view.width()
        click('workspaceSizeButton')
        assert controller.snapshot['activeContext'] == selected_before
        assert controller.snapshot['pageNumber'] == page_before
        capture('document_expanded.png')
        click('workspaceSizeButton')
        assert view.width() == base_width
        click('liveFoldButton')
        click('notice')
        assert controller.snapshot['activeContext'] == selected_before
        assert controller.snapshot['pageNumber'] == page_before
        assert find('draftEditor').property('text') == draft_before
        capture('document_restored.png')
        report['pdf_preserved'] = True
        report['pdf_sha256'] = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
        report['pdf_origin'] = 'https://arxiv.org/pdf/2506.22716; existing original PDF with repository provenance manifest'
    report['passed'] = True
except Exception as exc:
    report['passed'] = False
    report['failure'] = str(exc)
    capture('reading_verification_failure.png')
    raise
finally:
    app.clipboard().setText(clipboard_before)
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    controller.close()
    view.close()
