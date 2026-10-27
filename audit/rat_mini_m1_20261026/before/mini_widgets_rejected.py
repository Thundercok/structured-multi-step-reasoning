"""RAT Mini M1. Widgets only collect input/project shared execution results."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import threading
from uuid import uuid4

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QMessageBox, QPlainTextEdit, QPushButton, QSystemTrayIcon, QTextBrowser, QVBoxLayout, QWidget)

from rat.mini import MiniSession
from rat.engine.mini_settings import keychain_key, read_settings, save_settings


BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
MASCOT = BASE / 'rat/assets/rat_mascot_cutout.png'
STYLE = '''
QWidget { background:#FBF8F0; color:#29251E; font-family:-apple-system; font-size:13px; }
QPlainTextEdit,QTextBrowser,QListWidget,QLineEdit,QComboBox {background:#FFFFFF; border:1px solid #DCD3C1; border-radius:8px; padding:7px; selection-background-color:#D9E7DF;}
QPushButton {background:#F0E9D9; border:1px solid #D6C6A2; border-radius:8px; padding:8px 12px;}
QPushButton:hover {background:#E8DAB9;} QPushButton:disabled {color:#A69D8E;}
QPushButton#primary {background:#315C4C; color:white; border:0; font-weight:600;}
QLabel#quiet {color:#786F61;font-size:12px;} QLabel#badge {background:#E7EFE9;color:#315C4C;border-radius:7px;padding:5px;}
'''


class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle('Cài đặt RAT Mini')
        self.setMinimumWidth(570)
        self.settings = dict(settings)
        layout = QVBoxLayout(self)
        title = QLabel('Thư mục được phép tìm và lập chỉ mục')
        layout.addWidget(title)
        self.roots = QListWidget()
        self.roots.addItems(settings['roots'])
        self.roots.setMaximumHeight(100)
        layout.addWidget(self.roots)
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('Đường dẫn thư mục hoặc bấm Chọn…')
        row.addWidget(self.folder)
        choose = QPushButton('Chọn…')
        choose.clicked.connect(self.choose_folder)
        row.addWidget(choose)
        add = QPushButton('Thêm')
        add.clicked.connect(self.add_folder)
        row.addWidget(add)
        remove = QPushButton('Bỏ chọn')
        remove.clicked.connect(lambda: self.roots.takeItem(self.roots.currentRow()))
        row.addWidget(remove)
        layout.addLayout(row)
        self.semantic = QCheckBox('Bật tìm ngữ nghĩa local · model 135MB, chỉ tải vào RAM khi cần')
        self.semantic.setChecked(settings.get('semantic_enabled', False))
        layout.addWidget(self.semantic)
        layout.addWidget(QLabel('Chỉ mục cập nhật thủ công bằng “Lập chỉ mục”. Hỗ trợ TXT, Markdown và PDF có text.'))
        form = QFormLayout()
        self.provider = QComboBox()
        for label, value in [('OpenAI','openai'), ('DeepSeek','deepseek'), ('Groq','groq')]:
            self.provider.addItem(label, value)
        self.provider.setCurrentIndex(max(0, self.provider.findData(settings['provider'])))
        self.model = QLineEdit(settings['model'])
        self.model.setPlaceholderText('Model ID có hỗ trợ tool calling')
        form.addRow('Agent cloud', self.provider)
        form.addRow('Model ID', self.model)
        self.translation = QComboBox()
        for label, value in [('Apple (nếu sẵn sàng)','apple'), ('LLM cloud đã cấu hình','llm'),
                             ('DeepL API','deepl'), ('Google Cloud Translation','google'), ('MyMemory','mymemory')]:
            self.translation.addItem(label,value)
        self.translation.setCurrentIndex(max(0,self.translation.findData(settings['translation_provider'])))
        form.addRow('Backend dịch', self.translation)
        self.key_provider = QComboBox()
        for value in ('openai','deepseek','groq','deepl','google'):
            self.key_provider.addItem(value, value)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText('Để trống để giữ key cũ; không lưu key vào file cấu hình')
        form.addRow('Lưu key cho', self.key_provider)
        form.addRow('API key → Keychain', self.key)
        layout.addLayout(form)
        self.fallback = QCheckBox('Cho phép MyMemory · gửi đoạn cần dịch đến dịch vụ online này')
        self.fallback.setChecked(settings.get('free_fallback', False))
        layout.addWidget(self.fallback)
        notice = QLabel('Agent cloud nhận yêu cầu và metadata tên file; không gửi đường dẫn đầy đủ hoặc toàn bộ chỉ mục.\n'
                        'Backend dịch nhận đoạn bạn yêu cầu dịch. Bạn chọn nhà cung cấp và dùng key của mình.')
        notice.setWordWrap(True)
        notice.setObjectName('quiet')
        layout.addWidget(notice)
        save = QPushButton('Lưu cài đặt')
        save.setObjectName('primary')
        save.clicked.connect(self.accept_settings)
        layout.addWidget(save)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục RAT được phép tìm')
        if folder:
            self.folder.setText(folder)
            self.add_folder()

    def add_folder(self):
        path = Path(self.folder.text()).expanduser()
        if not self.folder.text().strip() or not path.is_dir():
            return
        value = str(path.resolve())
        if value not in [self.roots.item(i).text() for i in range(self.roots.count())]:
            self.roots.addItem(value)
        self.folder.clear()

    def accept_settings(self):
        try:
            if self.key.text().strip():
                keychain_key(self.key_provider.currentData(), self.key.text())
                self.key.clear()
            self.settings.update(roots=[self.roots.item(i).text() for i in range(self.roots.count())],
                provider=self.provider.currentData(), model=self.model.text().strip(),
                translation_provider=self.translation.currentData(), free_fallback=self.fallback.isChecked(),
                semantic_enabled=self.semantic.isChecked())
            save_settings(self.settings)
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, 'Chưa lưu được cài đặt', str(exc))


class MiniJob(QThread):
    result = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, session, operation, args, query, generation):
        super().__init__()
        self.session, self.operation, self.args, self.query = session, operation, args, query
        self.generation, self.stop = generation, threading.Event()

    def run(self):
        events = []
        try:
            progress = lambda text: self.progress.emit(text)
            operation, args = self.operation, self.args
            if operation == 'capture_translate':
                capture = self.session.execute('capture_text', {'mode': args['mode']},
                    cancel=self.stop.is_set, on_event=lambda event: events.append(event.to_dict()), progress=progress)
                if capture.error:
                    self.result.emit({'response': capture, 'events': events})
                    return
                artifact = next(a for a in capture.artifacts if a.kind == 'captured_text')
                args = {'source_ref': {'artifact_id': artifact.id, 'revision': artifact.revision},
                        'source_language': args.get('source_language', 'auto'), 'target_language': args['target_language']}
                operation = 'translate_text'
            response = self.session.execute(operation, args, query=self.query, cancel=self.stop.is_set,
                on_event=lambda event: events.append(event.to_dict()), progress=progress)
            value = {'response': response, 'events': events, 'operation': operation,
                     'llm_calls': self.session.client.calls}
            recording = os.environ.get('RAT_MINI_ACCEPTANCE_DIR')
            if recording:
                folder = Path(recording)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (response.execution_id + '.json')).write_text(json.dumps({
                    'query': self.query, 'operation': operation, 'args': args,
                    'answer': response.answer, 'error': response.error, 'events': events,
                    'artifacts': [a.to_dict() for a in response.artifacts],
                    'verification': response.verification_reports, 'llm_calls': self.session.client.calls,
                    'usage_unknown': self.session.client.usage_unknown}, ensure_ascii=False, default=str, indent=2))
            self.result.emit(value)
        except Exception as exc:
            self.result.emit({'error': str(exc), 'events': events})


class Mascot(QWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel, self.offset, self.moved = panel, None, False
        self.setWindowTitle('RAT Mini Mascot')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(108, 128)
        layout = QVBoxLayout(self)
        image = QLabel()
        image.setPixmap(QPixmap(str(MASCOT)).scaledToHeight(100, Qt.TransformationMode.SmoothTransformation))
        image.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        image.setStyleSheet('background:transparent;')
        layout.addWidget(image)
        self.setToolTip('RAT Mini M1 · bấm để mở · ⌥⇧D quét dịch')
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right()-145, screen.bottom()-170)

    def mousePressEvent(self, event):
        self.offset = event.globalPosition().toPoint() - self.pos()
        self.moved = False

    def mouseMoveEvent(self, event):
        if self.offset is not None:
            self.moved = True
            self.move(event.globalPosition().toPoint()-self.offset)

    def mouseReleaseEvent(self, event):
        if not self.moved:
            self.panel.present()
        self.offset = None


class MiniWindow(QWidget):
    hotkey = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = read_settings()
        self.session = MiniSession(self.settings)
        self.job, self.pending, self.generation = None, None, 0
        self.last_artifact = None
        self.quitting = False
        self.setWindowTitle('RAT Mini · M1')
        self.setMinimumSize(620, 570)
        self.resize(680, 650)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        header = QHBoxLayout()
        image = QLabel()
        image.setPixmap(QPixmap(str(MASCOT)).scaledToHeight(52, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(image)
        title = QLabel('RAT Mini')
        title.setStyleSheet('font-size:25px;font-weight:700;')
        header.addWidget(title)
        badge = QLabel('Mini M1 · Finder + Dịch')
        badge.setObjectName('badge')
        header.addWidget(badge)
        header.addStretch()
        self.settings_button = QPushButton('Cài đặt')
        self.settings_button.clicked.connect(self.configure)
        header.addWidget(self.settings_button)
        layout.addLayout(header)
        self.scope_label = QLabel()
        self.scope_label.setObjectName('quiet')
        self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText('Tìm file bằng tên hoặc mô tả…\nHoặc dán đoạn văn cần dịch vào đây.')
        self.input.setMaximumHeight(125)
        self.input.setAccessibleName('Nội dung yêu cầu')
        layout.addWidget(self.input)
        actions = QHBoxLayout()
        for label, callback in [('Tìm file', self.find), ('Dịch', self.translate),
                                ('Clipboard', lambda: self.capture('clipboard')),
                                ('Quét vùng ⌥⇧D', lambda: self.capture('region')),
                                ('Hỏi Agent', self.agent)]:
            button = QPushButton(label)
            if label == 'Tìm file':
                button.setObjectName('primary')
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel('Dịch từ'))
        self.source = QComboBox()
        self.source.addItem('Tự nhận diện', 'auto')
        self.target = QComboBox()
        for label, code in [('Tiếng Việt','vi'),('English','en'),('日本語','ja'),('한국어','ko'),('中文','zh'),('Français','fr'),('Deutsch','de')]:
            self.source.addItem(label, code)
            self.target.addItem(label, code)
        self.target.setCurrentIndex(max(0,self.target.findData(self.settings['target_language'])))
        language_row.addWidget(self.source)
        language_row.addWidget(QLabel('sang'))
        language_row.addWidget(self.target)
        language_row.addStretch()
        self.index_button = QPushButton('Lập chỉ mục')
        self.index_button.clicked.connect(self.index_files)
        language_row.addWidget(self.index_button)
        layout.addLayout(language_row)
        self.status = QLabel('Sẵn sàng · chọn thư mục hoặc nhập đoạn cần dịch.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.files = QListWidget()
        self.files.setAccessibleName('Kết quả tìm file')
        self.files.itemDoubleClicked.connect(lambda _: self.file_action('open_file'))
        layout.addWidget(self.files)
        self.output = QTextBrowser()
        self.output.setAccessibleName('Kết quả dịch hoặc Agent')
        self.output.setOpenExternalLinks(False)
        layout.addWidget(self.output)
        self.output.hide()
        footer = QHBoxLayout()
        for label, callback in [('Mở file', lambda: self.file_action('open_file')),
                                ('Hiện trong Finder', lambda: self.file_action('reveal_file')),
                                ('Sao chép', self.copy_result), ('Hủy', self.cancel)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            footer.addWidget(button)
        footer.addStretch()
        quit_button = QPushButton('Thoát')
        quit_button.clicked.connect(self.quit)
        footer.addWidget(quit_button)
        layout.addLayout(footer)
        hint = QLabel('⌘↵ tìm file · ⌥⇧D chọn vùng để dịch · Chỉ tìm trong thư mục bạn cho phép')
        hint.setObjectName('quiet')
        layout.addWidget(hint)
        QShortcut(QKeySequence('Ctrl+Return'), self, self.find)
        QShortcut(QKeySequence('Ctrl+Q'), self, self.quit)
        QShortcut(QKeySequence('Esc'), self, self.hide)
        self.hotkey.connect(lambda: self.capture('region'))
        self.mascot = Mascot(self)
        self.mascot.show()
        self.tray = QSystemTrayIcon(QIcon(str(MASCOT)), self)
        menu = QMenu()
        menu.addAction('Mở RAT Mini', self.present)
        menu.addAction('Dịch clipboard', lambda: self.capture('clipboard'))
        menu.addAction('Quét vùng ⌥⇧D', lambda: self.capture('region'))
        menu.addAction('Thoát', self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda *_: self.present())
        self._tray_menu = menu
        self.tray.show()
        self.update_scope()

    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def update_scope(self):
        roots = self.settings['roots']
        self.scope_label.setText('Phạm vi: ' + (' · '.join(roots) if roots else 'Chưa chọn — mở Cài đặt để thêm thư mục.'))
        self.index_button.setEnabled(bool(roots) and self.settings.get('semantic_enabled', False))

    def configure(self):
        if self.job is not None:
            self.status.setText('Hủy hoặc đợi tác vụ hiện tại trước khi đổi cài đặt.')
            return
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.session.scopes.set_roots([])  # revoke every old handle before replacing composition
            self.session.semantic.unload()
            self.settings = dialog.settings
            self.session = MiniSession(self.settings)
            self.last_artifact = None
            self.files.clear()
            self.update_scope()
            self.status.setText('Đã lưu. Bạn có thể tìm file hoặc dịch ngay.')

    def find(self):
        self.submit('find_files', {'query': self.input.toPlainText().strip()})

    def translate(self):
        self.submit('translate_text', {'text': self.input.toPlainText(),
                    'source_language': self.source.currentData(), 'target_language': self.target.currentData()})

    def agent(self):
        self.submit(None, {}, self.input.toPlainText().strip())

    def capture(self, mode):
        if mode == 'region':
            self.hide()
            self.mascot.hide()
        self.submit('capture_translate', {'mode': mode, 'source_language': self.source.currentData(),
                                         'target_language': self.target.currentData()})

    def index_files(self):
        self.submit('index_files', {})

    def submit(self, operation, args, query=''):
        if self.quitting:
            return
        self.generation += 1
        self.pending = (operation, args, query, self.generation)
        if self.job is not None:
            self.job.stop.set()
            self.status.setText('Đang hủy tác vụ trước…')
        else:
            self.start_pending()

    def start_pending(self):
        if not self.pending:
            return
        operation, args, query, generation = self.pending
        self.pending = None
        self.status.setStyleSheet('')
        self.status.setText('Đang thực hiện…')
        self.settings_button.setEnabled(False)
        job = MiniJob(self.session, operation, args, query, generation)
        self.job = job
        job.progress.connect(lambda text: self.status.setText(text) if job.generation == self.generation else None)
        job.result.connect(lambda value: self.render(value) if job.generation == self.generation else None)
        job.finished.connect(lambda: self.finished(job))
        job.start()

    def finished(self, job):
        self.job = None
        job.deleteLater()
        self.settings_button.setEnabled(True)
        if self.quitting:
            QApplication.quit()
        elif self.pending:
            self.start_pending()

    def render(self, value):
        self.present()
        self.mascot.show()
        response = value.get('response')
        error = value.get('error') or (response.error if response else None)
        if error:
            self.status.setText('Đã hủy.' if str(error).startswith('cancelled') else str(error))
            self.status.setStyleSheet('color:#9B4036;')
            return
        if response.pending_input_request:
            self.status.setText(response.pending_input_request.prompt)
            return
        artifacts = response.artifacts
        if artifacts:
            artifact = artifacts[-1]
            data = artifact.payload
            if artifact.kind == 'finder_results':
                self.last_artifact = artifact
                self.files.clear()
                self.files.show()
                self.output.hide()
                for hit in data['hits']:
                    item = QListWidgetItem(hit['title'] + '\n' + hit['path'] + '\n' + ' + '.join(hit['match_sources']))
                    item.setData(Qt.ItemDataRole.UserRole, hit['resource_id'])
                    self.files.addItem(item)
                if self.files.count():
                    self.files.setCurrentRow(0)
                self.status.setText(f"{len(data['hits'])} file · Phạm vi {data['coverage']['roots']} thư mục · "
                    + ('Tìm kiếm có giới hạn' if data['status'] == 'partial' else 'Đã kiểm tra file và quyền đọc'))
                return
            if artifact.kind == 'translation':
                self.input.setPlainText(data['source_text'])
                self.output.setPlainText(data['text'])
                self.output.show()
                self.files.hide()
                warnings = ' · '.join(data.get('warnings', []))
                self.status.setText(f"{data['source_language']} → {data['target_language']} · {data['provider']} · "
                    + ('Chưa dịch đủ' if data['status'] == 'partial' else 'Đã dịch') + (' · ' + warnings if warnings else ''))
                return
            if artifact.kind == 'index_receipt':
                self.status.setText(f"Đã lập chỉ mục {data['indexed_files']} file · {data['chunks']} đoạn · {data['skipped']} file bỏ qua. Cập nhật thủ công.")
                return
        if value.get('operation') in ('open_file', 'reveal_file'):
            self.status.setText(response.answer)
        else:
            self.output.setPlainText(response.answer)
            self.output.show()
            self.files.hide()
            self.status.setText(f"Agent · {value.get('llm_calls', 0)} lần gọi model · {response.answer_verification_status}")

    def file_action(self, operation):
        item = self.files.currentItem()
        if item and self.last_artifact:
            self.submit(operation, {'artifact_id': self.last_artifact.id, 'revision': self.last_artifact.revision,
                                    'resource_id': item.data(Qt.ItemDataRole.UserRole)})

    def copy_result(self):
        if self.output.isVisible():
            QApplication.clipboard().setText(self.output.toPlainText())
        elif self.files.currentItem() and self.last_artifact:
            selected = self.files.currentItem().data(Qt.ItemDataRole.UserRole)
            hit = next(h for h in self.last_artifact.payload['hits'] if h['resource_id'] == selected)
            QApplication.clipboard().setText(hit['path'])

    def cancel(self):
        self.generation += 1
        self.pending = None
        if self.job:
            self.job.stop.set()
        self.status.setText('Đã yêu cầu hủy.')

    def quit(self):
        self.quitting = True
        self.cancel()
        self.hide()
        self.mascot.hide()
        self.tray.hide()
        if self.job is None:
            QApplication.quit()

    def closeEvent(self, event):
        self.hide()
        event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('RAT Mini')
    app.setQuitOnLastWindowClosed(False)
    window = MiniWindow()
    window.show()
    try:
        from rat.os.mini_hotkey import register_hotkey
        register_hotkey(window.hotkey.emit)
    except Exception:
        window.status.setText('Hotkey đang bị chiếm; vẫn dùng nút Quét vùng được.')
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
