"""Measure how fast the RAT desk answers, so visual work cannot slow it down unnoticed.

Runs the real QML desk on a temporary home with sample files and never opens anything.
The global hotkey path through macOS is not covered: timing starts when the desk is asked to show.

    python tools/measure_desk_latency.py                 print the numbers
    python tools/measure_desk_latency.py --save          also store them as the baseline
    python tools/measure_desk_latency.py --compare       exit 1 if a step got slower than the baseline
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name('desk_latency_baseline.json')
SAMPLES = {
    'hop_dong.txt': 'Hợp đồng thuê nhà ký với chủ trọ, tiền cọc hai tháng, thanh toán đầu mỗi tháng.\n',
    'pho.txt': 'Công thức nấu phở bò với xương hầm và quế hồi.\n',
    'giai_tich.txt': 'Bài tập giải tích về đạo hàm và tích phân cho sinh viên năm nhất.\n',
}
# A step counts as slower only past both margins, so timer noise on small numbers is ignored.
ALLOWED_RATIO = 1.5
ALLOWED_EXTRA_MS = 10.0


def regressions(baseline, current):
    """Names of the steps whose median got slower than the baseline allows."""
    return [
        name for name, step in current.items()
        if name in baseline
        and step['median_ms'] > baseline[name]['median_ms'] * ALLOWED_RATIO
        and step['median_ms'] > baseline[name]['median_ms'] + ALLOWED_EXTRA_MS
    ]


def summarize(samples):
    return {'median_ms': round(statistics.median(samples), 1), 'first_ms': round(samples[0], 1),
            'worst_ms': round(max(samples), 1), 'runs': len(samples)}


def measure(runs):
    home = Path(tempfile.mkdtemp(prefix='rat-latency-'))
    (home / 'state').mkdir()
    (home / 'Documents').mkdir()
    for name, text in SAMPLES.items():
        (home / 'Documents' / name).write_text(text * 5, encoding='utf-8')
    os.environ.update(HOME=str(home), RAT_STATE_DIR=str(home / 'state'))
    sys.path.insert(0, str(ROOT))

    from PyQt6.QtCore import QObject, Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtTest import QTest

    app = QGuiApplication([sys.argv[0]])
    from rat.ui.quick_app import create_quick_desk

    def wait_until(done, timeout=20.0):
        deadline = time.perf_counter() + timeout
        while not done():
            if time.perf_counter() > deadline:
                raise TimeoutError('step did not finish')
            app.processEvents()
            time.sleep(0.001)

    frames = []
    started = time.perf_counter()
    view, controller = create_quick_desk(quit_on_close=False)
    view.frameSwapped.connect(lambda: frames.append(time.perf_counter()))
    view.show()
    wait_until(lambda: frames)
    results = {'open_desk': summarize([(frames[0] - started) * 1000])}

    opened = []
    controller._open_url = lambda url: opened.append(url) or True
    editor = view.rootObject().findChild(QObject, 'draftEditor')
    wait_until(lambda: controller._finder_semantic.count() >= len(SAMPLES), timeout=120.0)

    def clear_composer():
        editor.setProperty('text', '')
        wait_until(lambda: not controller.snapshot.get('finderHits'))
        opened.clear()
        frames.clear()

    def has_hits():
        return bool(controller.snapshot.get('finderHits'))

    def first_frame_after(action):
        frames.clear()
        start = time.perf_counter()
        action()
        wait_until(lambda: frames)
        return (frames[0] - start) * 1000

    editor.setProperty('text', 'cách nấu phở')
    start = time.perf_counter()
    wait_until(has_hits, timeout=60.0)
    results['first_search_cold_model'] = summarize([(time.perf_counter() - start) * 1000])

    summon, keystroke, hits, enter_ready, enter_pending = [], [], [], [], []
    for _ in range(runs):
        clear_composer()
        view.hide()
        app.processEvents()

        def show():
            view.show()
            view.raise_()
            view.requestActivate()
            editor.forceActiveFocus()
        summon.append(first_frame_after(show))

        editor.forceActiveFocus()
        keystroke.append(first_frame_after(lambda: QTest.keyClick(view, Qt.Key.Key_A)))

        clear_composer()
        editor.forceActiveFocus()
        start = time.perf_counter()
        editor.setProperty('text', 'cách nấu phở')
        wait_until(has_hits)
        hits.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        QTest.keyClick(view, Qt.Key.Key_Return)
        wait_until(lambda: opened)
        enter_ready.append((time.perf_counter() - start) * 1000)

        clear_composer()
        editor.forceActiveFocus()
        editor.setProperty('text', 'giấy tờ thuê phòng trọ')
        start = time.perf_counter()
        QTest.keyClick(view, Qt.Key.Key_Return)
        wait_until(lambda: opened)
        enter_pending.append((time.perf_counter() - start) * 1000)

    results.update(summon_to_frame=summarize(summon), keystroke_to_frame=summarize(keystroke),
                   typing_to_hits=summarize(hits), enter_opens_shown_hit=summarize(enter_ready),
                   enter_opens_before_hits=summarize(enter_pending))
    shutil.rmtree(home, ignore_errors=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--save', action='store_true', help='store these numbers as the baseline')
    parser.add_argument('--compare', action='store_true', help='exit 1 if slower than the baseline')
    args = parser.parse_args()

    results = measure(args.runs)
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {'commit': commit, 'machine': platform.platform(), 'qt_platform': os.environ.get('QT_QPA_PLATFORM', 'native'),
              'steps': results}
    for name, step in results.items():
        print(f"{name:26} {step['median_ms']:8.1f} ms   first {step['first_ms']:8.1f}   worst {step['worst_ms']:8.1f}   ({step['runs']} runs)")
    if args.save:
        BASELINE.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    status = 0
    if args.compare:
        slower = regressions(json.loads(BASELINE.read_text(encoding='utf-8'))['steps'], results)
        print('Slower than the baseline: ' + ', '.join(slower) if slower else 'Within the baseline.')
        status = 1 if slower else 0
    sys.stdout.flush()
    # Skip Qt teardown: the numbers are already out and the desk's workers need no clean exit here.
    os._exit(status)


if __name__ == '__main__':
    main()
