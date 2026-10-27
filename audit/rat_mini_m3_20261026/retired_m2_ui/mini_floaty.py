"""Original floaty mascot/bubble, projecting the shared two-capability service."""
from __future__ import annotations

import html
from pathlib import Path
import sys

from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QLockFile
from PyQt6.QtGui import QIcon, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication, QWidget, QFrame, QVBoxLayout, QLabel,
    QPushButton, QMenu, QSystemTrayIcon, QPlainTextEdit, QScrollArea, QHBoxLayout, QListWidget, QListWidgetItem)

from rat.mini import MiniSession
from rat.engine.mini_settings import read_settings, state_directory
from rat.os.mini_hotkey import register_hotkey
from rat.ui.mini_worker import MiniJob
from rat.ui.mini_settings_dialog import SettingsDialog

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
ASSET = BASE / 'rat/assets/rat_mascot_cutout.png'
HINT = 'Tìm file · Dịch văn bản online\nRAT Mini · M2'


class Floaty(QWidget):
    hotkey = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = read_settings()
        self.session = MiniSession(self.settings)
        self.job, self.pending, self.generation, self.quitting = None, None, 0, False
        self.finder_artifact, self.output_text, self.mode = None, '', 'find'
        self.drag_offset, self.moved = None, False
        self.setWindowTitle('RAT Mini · Floaty M2')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.paper = QFrame()
        self.paper.setObjectName('paper')
        self.paper.setStyleSheet('''QFrame#paper{background:#FFFDF9;border:1px solid #DEC88E;border-bottom:3px solid #C9A952;border-radius:14px;}
            QLabel{background:transparent;color:#1F1A16;border:0;font-size:14px;}
            QPlainTextEdit{background:#FAF7EF;color:#1F1A16;border:1px solid #E2D8BF;border-radius:7px;padding:5px;}
            QScrollArea,QScrollArea>QWidget>QWidget{background:transparent;border:0;}''')
        paper = QVBoxLayout(self.paper)
        paper.setContentsMargins(13, 12, 13, 12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.bubble = QLabel()
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.bubble.setOpenExternalLinks(False)
        self.bubble.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bubble.customContextMenuRequested.connect(self.bubble_menu)
        self.bubble.linkActivated.connect(self.link)
        self.scroll.setWidget(self.bubble)
        paper.addWidget(self.scroll)
        self.files = QListWidget()
        self.files.setWordWrap(True)
        self.files.setAccessibleName('Kết quả Spotlight')
        self.files.setStyleSheet('QListWidget{background:#FFFDF9;border:0;color:#1F1A16;font-size:12px;}')
        self.files.hide()
        self.files.itemActivated.connect(lambda item:self.open_file(item.data(Qt.ItemDataRole.UserRole)))
        paper.addWidget(self.files)
        self.editor = QPlainTextEdit()
        self.editor.setAccessibleName('Yêu cầu RAT Mini')
        self.editor.setFixedHeight(72)
        self.editor.installEventFilter(self)
        self.files.installEventFilter(self)
        self.editor.setPlaceholderText('Tên file hoặc nội dung cần dịch…')
        paper.addWidget(self.editor)
        actions = QHBoxLayout()
        for text, callback in [('Tìm file',lambda:self.submit_editor('find')),
                               ('Dịch',lambda:self.submit_editor('translate')),
                               ('Dịch Clipboard',lambda:self.capture('clipboard'))]:
            button = QPushButton(text)
            button.setStyleSheet('QPushButton{background:#F0E9D9;color:#443D31;border:0;border-radius:6px;padding:5px;font-size:11px;}')
            button.clicked.connect(callback)
            actions.addWidget(button)
        paper.addLayout(actions)
        layout.addWidget(self.paper)
        self.rat = QLabel()
        self.rat.setPixmap(QPixmap(str(ASSET)).scaledToHeight(130, Qt.TransformationMode.SmoothTransformation))
        self.rat.setStyleSheet('background:transparent;')
        self.rat.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.rat.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.rat, alignment=Qt.AlignmentFlag.AlignHCenter)
        close = QPushButton('×', self)
        close.setFixedSize(20, 20)
        close.setStyleSheet('background:#F0ECE4;border:1px solid #D6CEBE;border-radius:10px;color:#4B4339;')
        close.move(self.width()-24, 0)
        close.clicked.connect(self.hide)
        self.hotkey.connect(lambda: self.capture('region'))
        QShortcut(QKeySequence('Esc'), self, self.hide)
        QShortcut(QKeySequence('Ctrl+Q'), self, self.quit)
        self.tray = QSystemTrayIcon(QIcon(str(ASSET)), self)
        self.tray_menu = self.menu()
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(lambda *_: self.present())
        self.tray.show()
        self.set_bubble(HINT)

    def set_bubble(self, text, rich=False):
        self.bubble.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
        self.bubble.setText(text)
        self.bubble.setFixedWidth(304)
        self.bubble.adjustSize()
        self.scroll.setFixedHeight(max(44, min(270, self.bubble.height()+5)))
        self.adjustSize()
        screen = self.screen().availableGeometry()
        self.move(max(screen.left(), min(self.x(), screen.right()-self.width())),
                  max(screen.top(), min(self.y(), screen.bottom()-self.height())))

    def present(self, activate=True):
        self.show()
        self.raise_()
        if activate:
            self.activateWindow()

    def menu(self):
        menu = QMenu(self)
        menu.addAction('Hiện RAT Mini', self.present)
        menu.addAction('Tìm file…', lambda: self.compose('find'))
        menu.addAction('Dịch văn bản…', lambda: self.compose('translate'))
        menu.addAction('Dịch clipboard', lambda: self.capture('clipboard'))
        menu.addAction('Quét vùng (⌥⇧D)', lambda: self.capture('region'))
        menu.addAction('Hỏi Agent cloud…', lambda: self.compose('agent'))
        menu.addSeparator()
        menu.addAction('Sao chép kết quả', lambda: QApplication.clipboard().setText(self.output_text))
        menu.addAction('Cài đặt…', self.configure)
        menu.addAction('Hủy tác vụ', self.cancel)
        menu.addAction('Ẩn chuột', self.hide)
        menu.addAction('Thoát', self.quit)
        return menu

    def contextMenuEvent(self, event):
        menu = self.menu()
        menu.exec(event.globalPos())
        menu.deleteLater()

    def bubble_menu(self, point):
        menu = self.menu()
        menu.exec(self.bubble.mapToGlobal(point))
        menu.deleteLater()

    def compose(self, mode):
        self.mode = mode
        self.editor.setPlaceholderText({'find':'Tên hoặc mô tả file · ↵ tìm',
            'translate':'Đoạn cần dịch · ↵ dịch · ⇧↵ xuống dòng', 'agent':'Yêu cầu tìm file/dịch · cần API key'}[mode])
        self.editor.show()
        self.set_bubble({'find':'Bạn muốn tìm file nào?', 'translate':'Dịch đoạn văn', 'agent':'Nhờ Agent tìm file hoặc dịch'}[mode])
        self.present()
        self.editor.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.files and event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.files.currentItem()
            if item is not None:
                self.open_file(item.data(Qt.ItemDataRole.UserRole))
            return True
        if obj is self.editor and event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submit_editor(self.mode)
            return True
        return super().eventFilter(obj, event)

    def submit_editor(self, mode):
        self.mode = mode
        text = self.editor.toPlainText().strip()
        if not text:
            return
        if mode == 'translate':
            self.submit('translate_text', {'text':text, 'source_language':self.settings.get('source_language','auto'),
                'target_language':self.settings['target_language']}, text)
        elif mode == 'agent':
            self.submit(None, {}, text)
        else:
            self.submit('find_files', {'query':text}, text)

    def capture(self, mode):
        if mode == 'region':
            self.hide()
        args = {'mode':mode, 'source_language':self.settings.get('source_language','auto'),
                'target_language':self.settings['target_language']}
        if mode == 'clipboard':
            args['clipboard_text'] = QApplication.clipboard().text()
        self.submit('capture_translate', args)

    def submit(self, operation, args, query=''):
        if self.quitting:
            return
        self.generation += 1
        self.pending = operation, args, query, self.generation
        if self.job:
            self.job.stop.set()
        else:
            self.start_pending()

    def start_pending(self):
        operation, args, query, generation = self.pending
        self.pending = None
        self.files.hide()
        self.set_bubble('Đang thực hiện…')
        job = MiniJob(self.session, operation, args, query, generation)
        self.job = job
        job.progress.connect(lambda text: self.set_bubble(text) if job.generation == self.generation else None)
        job.result.connect(lambda value: self.render(value) if job.generation == self.generation else None)
        job.finished.connect(lambda: self.finished(job))
        job.start()

    def finished(self, job):
        self.job = None
        job.deleteLater()
        if self.quitting:
            QApplication.quit()
        elif self.pending:
            self.start_pending()

    def render(self, value):
        self.present(activate=False)
        response = value.get('response')
        error = value.get('error') or (response.error if response else None)
        if error:
            self.set_bubble('Đã hủy.' if str(error).startswith('cancelled') else str(error))
            return
        if response.pending_input_request:
            self.set_bubble(response.pending_input_request.prompt)
            return
        for artifact in reversed(response.artifacts):
            data = artifact.payload
            if artifact.kind == 'finder_results':
                self.finder_artifact = artifact
                self.output_text = '\n'.join(h['path'] for h in data['hits'])
                self.files.clear()
                for i, hit in enumerate(data['hits']):
                    item=QListWidgetItem(hit['title']+'\n'+hit['path'])
                    item.setData(Qt.ItemDataRole.UserRole,i)
                    self.files.addItem(item)
                self.set_bubble(f"{len(data['hits'])} file · ↑↓ chọn · Enter mở" if data['hits'] else
                                'Chưa tìm thấy. Kiểm tra phạm vi thư mục trong Cài đặt.')
                if data['hits']:
                    self.files.setFixedHeight(min(185,max(60,len(data['hits'])*55)))
                    self.files.show()
                    self.files.setCurrentRow(0)
                    self.files.setFocus()
                    self.adjustSize()
                return
            if artifact.kind == 'translation':
                self.output_text = data['text']
                meta = f"{data['source_language']} → {data['target_language']} · {data['provider']}"
                warning = ('Chưa dịch đủ. ' if data['status'] == 'partial' else '') + ' · '.join(data.get('warnings', []))
                self.set_bubble(html.escape(data['text']).replace('\n','<br>') +
                    '<br><br><small>'+html.escape(meta+' · '+warning)+'</small>', True)
                return
            if artifact.kind == 'index_receipt':
                self.set_bubble(f"Đã lập chỉ mục {data['indexed_files']} file · {data['chunks']} đoạn.\n"
                                f"{data['skipped']} file bỏ qua. Cập nhật thủ công.")
                return
        self.output_text = response.answer
        self.set_bubble(response.answer or 'Thao tác đã kết thúc.')

    def link(self, value):
        if not self.finder_artifact:
            return
        action, index = value.split(':', 1)
        if action not in ('open','reveal') or not index.isdigit():
            return
        hits = self.finder_artifact.payload['hits']
        if int(index) >= len(hits):
            return
        self.submit('open_file' if action == 'open' else 'reveal_file', {
            'artifact_id':self.finder_artifact.id, 'revision':self.finder_artifact.revision,
            'resource_id':hits[int(index)]['resource_id']})

    def open_file(self,index):
        self.link('open:'+str(index))

    def configure(self):
        if self.job:
            self.set_bubble('Hủy hoặc đợi tác vụ hiện tại trước khi đổi cài đặt.')
            return
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.session.scopes.set_roots([])
            self.settings = dialog.settings
            self.session = MiniSession(self.settings)
            self.finder_artifact = None
            self.tray_menu = self.menu()
            self.tray.setContextMenu(self.tray_menu)
            self.set_bubble('Đã lưu.\nNhập nội dung rồi chọn Tìm file hoặc Dịch. · M2')

    def cancel(self):
        self.generation += 1
        self.pending = None
        if self.job:
            self.job.stop.set()
        self.set_bubble('Đã yêu cầu hủy.')

    def quit(self):
        self.quitting = True
        self.cancel()
        self.hide()
        self.tray.hide()
        if not self.job:
            QApplication.quit()

    def mousePressEvent(self, event):
        self.drag_offset = event.globalPosition().toPoint()-self.pos()
        self.moved = False

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None:
            self.moved = True
            self.move(event.globalPosition().toPoint()-self.drag_offset)

    def mouseReleaseEvent(self, event):
        if not self.moved and event.button() == Qt.MouseButton.LeftButton:
            self.compose('find')
        self.drag_offset = None


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('RAT Mini')
    app.setQuitOnLastWindowClosed(False)
    state_directory().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(state_directory()/'mini.lock'))
    if not lock.tryLock():
        raise SystemExit('RAT Mini đã chạy; dùng biểu tượng trên menu bar để hiện chuột.')
    window = Floaty()
    window.show()
    try:
        register_hotkey(window.hotkey.emit)
    except Exception:
        window.set_bubble('Hotkey đang bị chiếm.\nChuột phải → Quét vùng vẫn dùng được. · M1')
    app._refs = (window, lock)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
