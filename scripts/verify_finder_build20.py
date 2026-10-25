"""Live Finder smoke: installed apps + existing read-only index, no model fixtures.

Run from repository root using the desktop Qt backend. Saves actual QQuickView
captures and local timings. Does not launch apps, extract files, or call a model.
"""
from pathlib import Path
import json
import math
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'artifacts/finder_build20_20261025'
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('RAT_STATE_DIR', str(OUT / 'state'))
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PyQt6.QtCore import QPointF, QUrl, Qt
from PyQt6.QtQuick import QQuickItem, QQuickView
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QGuiApplication
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import ProgressiveSearch, SearchRequest
from rat.ui.icon_provider import RatIconProvider
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window


def stats(values):
    ordered = sorted(values)
    return {'n': len(values), 'median_ms': ordered[len(values) // 2],
            'p95_ms': ordered[math.ceil(len(values) * .95) - 1], 'max_ms': max(values)}


app = QGuiApplication(sys.argv)
tick = time.perf_counter()
catalog = ApplicationCatalog.scan(use_cache=False)
scan_ms = (time.perf_counter() - tick) * 1000
index = Path.home() / '.rat/rat_index.db'
engine = ProgressiveSearch(index, catalog=catalog)
report = {'build': '2026.10.25.20', 'catalog_scan_ms': scan_ms,
          'installed_apps': len(catalog.applications), 'index_bytes': index.stat().st_size,
          'model_requests': 0, 'app_launches': 0,
          'timing_scope': 'Local measured lookup and input-to-QML delivery; not model latency or IME acceptance.',
          'queries': {}}
queries = ['mở cái app tính toán', 'mở trình duyệt', 'mở app gõ code',
           'tìm file quy chế tín chỉ', 'slide mạng máy tính', 'tìm file']
for query in queries:
    timings = []
    for i in range(31):
        snap = engine.initial(SearchRequest(i, query, limit=5))
        timings.append(snap.elapsed_ms)
    report['queries'][query] = {'first_ms': timings[0], 'warm': stats(timings[1:]),
                                'hits': len(snap.hits), 'errors': snap.errors}
engine.close_connection()

controller = QuickPDFController(finder_catalog=catalog, db_path=str(index), auto_init_finder=False)
controller.ready()
view = QQuickView()
view.setColor(Qt.GlobalColor.transparent)
RatIconProvider.register(view.engine(), 'icon')
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.setInitialProperties({'liveController': controller, 'reduceMotion': True})
view.setSource(QUrl.fromLocalFile(str(ROOT / 'rat/ui/quick/PDFDesk.qml')))
assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]
view.setTitle('RAT Finder — Build .20 live verification')
view.resize(520, 550)
window_timer = bind_desk_window(view)
view.show()
view.requestActivate()
QTest.qWait(250)
root = view.rootObject()


def find(name):
    pending = [root]
    while pending:
        item = pending.pop()
        if item.objectName() == name:
            return item
        pending.extend(item.childItems())
    raise AssertionError(name)


editor = find('draftEditor')
query = 'mo cai app tinh toan'
ui_times = []
try:
    # Native QTest key events type the unaccented equivalent. No injected hits.
    # Avoid claiming coverage of macOS Vietnamese input method behavior.
    for _ in range(10):
        editor.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(view, Qt.Key.Key_Backspace)
        QTest.qWait(20)
        tick = time.perf_counter()
        for char in query:
            QTest.keyClick(view, Qt.Key(ord(char.upper())))
        deadline = time.perf_counter() + 3
        while controller.snapshot['finderQuery'] != query or not controller.snapshot['finderHits']:
            assert time.perf_counter() < deadline, {'editor': editor.property('text'), 'query': controller.snapshot['finderQuery'], 'hits': len(controller.snapshot['finderHits'])}
            QTest.qWait(1)
        QGuiApplication.processEvents()
        ui_times.append((time.perf_counter() - tick) * 1000)
    assert controller.snapshot['finderHits'][0]['bundle_id'] == 'com.apple.calculator'
    assert find('finderMatchReason_0').property('text').startswith('Khớp công dụng')
    report['input_to_qml'] = stats(ui_times)
    assert view.grabWindow().save(str(OUT / 'finder_compact.png'))
    drawer = find('finderDrawerTab')
    if drawer.isVisible():
        point = drawer.mapToScene(QPointF(drawer.width() / 2, drawer.height() / 2)).toPoint()
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        QTest.qWait(200)
    assert find('finderMatchReason_0').isVisible()
    for width in (520, 700):
        view.resize(width, 550)
        QTest.qWait(200)
        assert view.grabWindow().save(str(OUT / f'finder_{width}.png'))
    QTest.keyClick(view, Qt.Key.Key_Down)
    QTest.keyClick(view, Qt.Key.Key_Escape)
    QTest.qWait(80)
    assert editor.property('text') == query
    report['escape_preserves_draft'] = True
    assert view.grabWindow().save(str(OUT / 'finder_dismissed.png'))
    report["ui_verified"] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))
except Exception as exc:
    report["ui_verified"] = False
    report["failure"] = str(exc)
    view.grabWindow().save(str(OUT / "finder_failure.png"))
    raise
finally:
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    controller.close()
    view.close()
