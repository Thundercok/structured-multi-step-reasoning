"""Explicit configuration dialog for the floaty product, no business execution."""
from pathlib import Path
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QLabel,QListWidget,QHBoxLayout,QLineEdit,QPushButton,QFileDialog,QCheckBox,QFormLayout,QComboBox,QMessageBox)
from rat.engine.mini_settings import save_settings,keychain_key

class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle('Cài đặt RAT Mini')
        self.setMinimumWidth(570)
        self.settings = dict(settings)
        self.setStyleSheet('QDialog{background:#FFFDF9;color:#29251E;} QLineEdit,QListWidget,QComboBox{padding:5px;} QPushButton{padding:6px 10px;}')
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
        self.semantic.setChecked(False)
        self.semantic.hide()
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
        for label, value in [('Google Translate online','google_gtx'), ('LLM cloud đã cấu hình','llm'),
                             ('DeepL API','deepl'), ('Google Cloud Translation','google'), ('MyMemory','mymemory')]:
            self.translation.addItem(label,value)
        self.translation.setCurrentIndex(max(0,self.translation.findData(settings['translation_provider'])))
        form.addRow('Backend dịch', self.translation)
        self.source = QComboBox()
        self.target = QComboBox()
        self.source.addItem('Tự nhận diện', 'auto')
        for label, code in [('Tiếng Việt','vi'),('English','en'),('日本語','ja'),('한국어','ko'),('中文','zh'),('Français','fr'),('Deutsch','de')]:
            self.source.addItem(label,code)
            self.target.addItem(label,code)
        self.source.setCurrentIndex(max(0,self.source.findData(settings.get('source_language','auto'))))
        self.target.setCurrentIndex(max(0,self.target.findData(settings.get('target_language','vi'))))
        form.addRow('Ngôn ngữ nguồn',self.source)
        form.addRow('Dịch sang',self.target)
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
            self.settings.update(source_language=self.source.currentData(),target_language=self.target.currentData())
            save_settings(self.settings)
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, 'Chưa lưu được cài đặt', str(exc))
