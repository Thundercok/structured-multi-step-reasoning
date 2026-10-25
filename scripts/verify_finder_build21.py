"""Desktop smoke using installed browsers, native key events and real OS open.

No assistant fixtures or model calls. The missing-app check exercises the public
launch slot with a genuinely absent path; it does not delete an installed app.
"""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'artifacts/finder_build21_20261025'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('RAT_STATE_DIR', str(OUT / 'state'))
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtQuick import QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QGuiApplication
from AppKit import NSWorkspace
from rat.engine.app_resolver import ApplicationCatalog
from rat.ui.icon_provider import RatIconProvider
from rat.ui.quick_app import bind_desk_window
from rat.ui.quick_pdf_controller import QuickPDFController

app = QGuiApplication(sys.argv)
catalog = ApplicationCatalog.scan(use_cache=False)
controller = QuickPDFController(finder_catalog=catalog, auto_init_finder=False,
                               db_path=str(Path.home() / '.rat/rat_index.db'))
controller.ready()
view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
RatIconProvider.register(view.engine(), 'icon')
view.setInitialProperties({'liveController': controller, 'reduceMotion': True})
view.setSource(QUrl.fromLocalFile(str(ROOT / 'rat/ui/quick/PDFDesk.qml')))
assert view.status() == QQuickView.Status.Ready
view.setTitle('RAT Finder — Build .21 live verification')
view.resize(520, 550)
window_timer = bind_desk_window(view)
view.show()
view.requestActivate()
QTest.qWait(250)
root = view.rootObject()
report = {'build': '2026.10.25.21', 'model_requests': 0,
          'input': 'native QTest ASCII key events, not Vietnamese IME acceptance',
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
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
    QTest.qWait(150)


def capture(name):
    QTest.qWait(150)
    assert view.grabWindow().save(str(OUT / name))
    report['screenshots'].append(name)


def running_ids():
    return {str(a.bundleIdentifier()) for a in NSWorkspace.sharedWorkspace().runningApplications()}


try:
    editor = find('draftEditor')
    editor.forceActiveFocus()
    query = 'mo trinh duyet'
    for char in query:
        QTest.keyClick(view, Qt.Key(ord(char.upper())))
    deadline = time.perf_counter() + 4
    while (controller.snapshot['finderQuery'] != query
           or not controller.snapshot['finderHits']
           or not all(h['kind'] == 'application' for h in controller.snapshot['finderHits'])):
        assert time.perf_counter() < deadline, 'no live browser candidates'
        QTest.qWait(5)
    if find('finderDrawerTab').isVisible():
        click('finderDrawerTab')
    hits = controller.snapshot['finderHits'][:3]
    assert len(hits) >= 2, 'multiple installed browser choices required for this smoke'
    report['candidates'] = [{'title': h['title'], 'bundle_id': h['bundle_id']} for h in hits]
    running_before = running_ids()
    # Prefer a browser already running to preserve the user's desktop session.
    chosen = next((i for i, h in enumerate(hits) if h['bundle_id'] in running_before), 0)
    for _ in range(chosen + 1):
        QTest.keyClick(view, Qt.Key.Key_Down)
    assert root.property('selectedFinderIndex') == chosen
    capture('browser_selected_520.png')
    tick = time.perf_counter()
    QTest.keyClick(view, Qt.Key.Key_Return)
    QTest.qWait(100)
    feedback = controller.snapshot['launchFeedback']
    assert feedback == f"Đã gửi yêu cầu mở {hits[chosen]['title']}."
    assert not controller.snapshot['launchFeedbackError']
    assert editor.property('text') == query
    report['launch'] = {'target': hits[chosen]['title'], 'bundle_id': hits[chosen]['bundle_id'],
                        'already_running': hits[chosen]['bundle_id'] in running_before,
                        'request_accepted': True, 'feedback': feedback,
                        'key_to_checked_feedback_ms': (time.perf_counter() - tick)*1000,
                        'timing_note': 'Includes 100ms observation wait; not app startup latency.'}
    deadline = time.perf_counter() + 5
    while hits[chosen]['bundle_id'] not in running_ids() and time.perf_counter() < deadline:
        QTest.qWait(100)
    report['launch']['running_after'] = hits[chosen]['bundle_id'] in running_ids()
    assert report['launch']['running_after']
    assert find('applicationLaunchFeedback').isVisible()
    capture('browser_opened_520.png')
    view.resize(700, view.height())
    capture('browser_opened_700.png')
    click('liveFoldButton')
    capture('browser_opened_compact.png')
    assert editor.property('text') == query

    # Real absent-path rejection, shown on the live UI. No stale hits fabricated.
    missing = OUT / 'RAT Missing Application.app'
    assert not missing.exists()
    assert not controller.launchApplication(str(missing))
    assert controller.snapshot['launchFeedbackError']
    assert editor.property('text') == query
    report['missing_app'] = {'path': str(missing), 'feedback': controller.snapshot['launchFeedback'],
                             'scope': 'public launch slot; not selection from a fabricated stale result'}
    capture('missing_app_error.png')
    editor.forceActiveFocus()
    QTest.keyClick(view, Qt.Key.Key_Space)
    assert not controller.snapshot['launchFeedback']
    report['draft_preserved'] = True
    report['feedback_clears_on_edit'] = True
    report['passed'] = True
except Exception as exc:
    report['passed'] = False
    report['failure'] = str(exc)
    capture('verification_failure.png')
    raise
finally:
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    controller.close()
    view.close()
