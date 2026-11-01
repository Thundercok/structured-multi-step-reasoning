"""Record a real-window RAT Lite walkthrough: real QML, real controller, real tools.

Typing goes through Qt key events into the composer; results come from the
local meaning index and on-device translation. Frames are grabbed from the
app's own window (no screen-recording permission) and joined with ffmpeg.

    python scripts/record_rat_lite_demo.py --root "/Users/Shared/RAT Lite demo" --out audit/<dir>
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

parser = argparse.ArgumentParser()
parser.add_argument('--root', required=True)
parser.add_argument('--out', required=True)
args = parser.parse_args()
out = Path(args.out); frames = out / 'frames'
shutil.rmtree(frames, ignore_errors=True); frames.mkdir(parents=True)
os.environ.setdefault('RAT_MINI_STATE_DIR', tempfile.mkdtemp(prefix='rat-lite-demo-'))

from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest
from rat.engine.mini_settings import DEFAULTS
from rat.ui.mini_quick import create_mini_desk

app = QGuiApplication(sys.argv)
view, c = create_mini_desk(dict(DEFAULTS, roots=[args.root], setup_completed=True, permission_hello_version=1))
view.setGeometry(80, 80, 620, 520); view.show()
root = view.rootObject()
count = 0
log = []


def grab():
    global count
    view.grabWindow().save(str(frames / f'{count:05d}.png')); count += 1


timer = QTimer(); timer.timeout.connect(grab); timer.start(100)


def wait(ms):
    # Each new task clears the pin, so hold it on while recording.
    end = time.time() + ms / 1000
    while time.time() < end:
        if not c.snapshot['pinned']:
            c.update(pinned=True)
        QTest.qWait(min(50, ms))


def until_idle(limit=60):
    started = time.time(); wait(200)
    while c.snapshot['busy'] and time.time() - started < limit:
        wait(100)
    wait(900)


def still(name):
    view.grabWindow().save(str(out / f'{name}.png'))
    s = c.snapshot
    hits = [h['title'] for h in s['finderHits']][:3]
    log.append(f"{name}: view={s['view']} phase={s['phase']} title_hits={hits} text={s['text'][:80]!r} status={s['status'][:80]!r}")


def type_and_send(text):
    root.focusComposer(); wait(150)
    editor = root.findChild(QObject, 'miniEditor')
    for ch in text:
        # Character by character into the real QML text field; its onTextChanged
        # drives the controller exactly as typing does. OS key routing is not exercised.
        QMetaObject.invokeMethod(editor, 'insert', Q_ARG(int, len(editor.property('text'))), Q_ARG(str, ch))
        wait(35)
    wait(400)
    c.submitDraft(); until_idle()


# Keep the panel open while recording: a click elsewhere on the screen would
# otherwise dismiss it, which is the intended behaviour for real use.
c.update(pinned=True)
c.summonMinimal(); wait(500)
c.session.semantic.start(c.session.scopes.roots)
while c.session.semantic.progress()['state'] not in ('ready', 'unavailable'):
    c.refresh_index_progress(); wait(200)
c.refresh_index_progress(); c.summonMinimal(); wait(800); still('01_empty')

type_and_send('tìm bài báo về cơ chế attention'); still('02_find_attention_paper')
type_and_send('tìm báo cáo đồ án nhóm 4'); still('03_find_group_report')
type_and_send('tìm cái lịch phòng thi môn giải tích'); still('04_find_exam_schedule')
type_and_send('dịch Multi-head self-attention lets every position look at every other position, which makes training highly parallel.')
still('05_translation')
root.setProperty('showSourceText', True); wait(1200); still('06_translation_source')
clipboard = QGuiApplication.clipboard(); previous = clipboard.text()
clipboard.setText('The model reaches better translation quality than recurrent baselines at a fraction of the training cost.')
c.translateClipboard(); until_idle(); still('07_clipboard_translation')
clipboard.setText(previous)
type_and_send('xin chào các bạn'); still('08_clarify_buttons')
c.submit('dịch'); until_idle(); still('09_after_choosing_translate')
type_and_send('dịch 这是一个测试句子'); still('10_unsupported_language')
root.openSettings(); wait(1500); still('11_settings')
timer.stop()

(out / 'run_log.txt').write_text('\n'.join(log) + '\n')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '10', '-i', str(frames / '%05d.png'),
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2:color=white', '-pix_fmt', 'yuv420p', str(out / 'rat_lite_demo.mp4')], check=True)
shutil.rmtree(frames)
print('\n'.join(log))
print('video', out / 'rat_lite_demo.mp4', 'frames', count)
