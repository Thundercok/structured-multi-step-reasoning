"""Mini projection of the existing RAT PDFDesk UI; all operations use shared tools."""
from __future__ import annotations

import html
from pathlib import Path
import re

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from rat.mini import MiniSession
from rat.engine.mini_settings import read_settings, save_settings, keychain_key
from rat.ui.mini_worker import MiniJob


class MiniController(QObject):
    changed = pyqtSignal()
    settingsChanged = pyqtSignal()
    showRequested = pyqtSignal()
    hideRequested = pyqtSignal()
    quitRequested = pyqtSignal()
    copyConfirmed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = read_settings()
        self.session = MiniSession(self.config)
        self.job, self.pending, self.generation, self.quitting = None, None, 0, False
        self.finder_artifact = None
        strings = ('answerExcerpt answerHtml answerHtmlDark answerText answerReadScope answerVerification '
            'errorCode errorText fileName finderFeedback launchFeedback matchedQuery matchedSnippet '
            'matchedSnippetHtml oneLineAnswer pageLabel pageReadingText pageText previewSnippet '
            'query rawMatchedSnippet searchQuery sourceKind title userQuery').split()
        self.state = {key: '' for key in strings}
        self.state.update(phase='idle', view='none', expanded=False, unread=False, busy=False,
            hasWorkbench=False, workspaceMode='single', canBack=False, canBackToAnswer=False,
            canCopy=False, hasMatchedSnippet=False, answerPreviewIsCode=False, pageTruncated=False,
            matchedSnippetTruncated=False, launchFeedbackError=False, pageCount=0, pageNumber=0,
            nextPage=0, previewPageNumber=0, items=[], installedApps=[], finderHits=[], events=[],
            processSteps=[], quickPrompts=[], readingSession={}, activeContext=None,
            answerSources=[], answerOutcome='completed', operationMode='find',
            status='Tìm file và dịch đoạn văn · mở Cài đặt để chọn thư mục và backend.')

    @pyqtProperty('QVariantMap', notify=changed)
    def snapshot(self):
        return self.state

    @pyqtProperty('QVariantMap', notify=settingsChanged)
    def settings(self):
        return self.config

    def update(self, **values):
        self.state.update(values)
        self.changed.emit()

    @pyqtSlot(str)
    def setMode(self, mode):
        if mode in ('find', 'translate', 'agent'):
            self.update(operationMode=mode)

    @pyqtSlot(str)
    def onComposerTextChanged(self, text):
        pass  # Do not run searches/models on each keystroke.

    @pyqtSlot(str)
    def submitQuery(self, text):
        text = text.strip()
        if not text:
            return
        mode = self.state['operationMode']
        match = re.match(r'^(?:dịch|translate)\s*[:：]?\s+(.+)', text, re.I | re.S)
        if match and mode != 'agent':
            mode, text = 'translate', match.group(1)
        if mode == 'translate':
            self.submit('translate_text', {'text': text, 'source_language': self.config.get('source_language', 'auto'),
                                         'target_language': self.config['target_language']}, text)
        elif mode == 'agent':
            self.submit(None, {}, text)
        else:
            self.submit('find_files', {'query': text}, text)

    @pyqtSlot(str)
    def search(self, text):
        self.submitQuery(text)

    @pyqtSlot(str)
    def capture(self, mode):
        if mode == 'region':
            self.hideRequested.emit()
        self.submit('capture_translate', {'mode': mode,
            'source_language': self.config.get('source_language', 'auto'), 'target_language': self.config['target_language']})

    @pyqtSlot()
    def indexFiles(self):
        self.submit('index_files', {}, 'Lập chỉ mục ngữ nghĩa các thư mục đã chọn')

    @pyqtSlot('QVariantMap', result=bool)
    def configure(self, changes):
        if self.job:
            self.update(finderFeedback='Hủy hoặc đợi tác vụ hiện tại trước khi đổi cài đặt.')
            return False
        try:
            values = dict(changes)
            key = values.pop('api_key', '')
            key_provider = values.pop('key_provider', 'openai')
            if key:
                keychain_key(key_provider, key)
            roots = [str(Path(p).expanduser().resolve()) for p in values.get('roots', []) if p.strip()]
            if any(not Path(p).is_dir() for p in roots):
                raise ValueError('Thư mục không tồn tại.')
            values['roots'] = roots
            new = {**self.config, **values}
            save_settings(new)
            self.session.scopes.set_roots([])
            self.session.semantic.unload()
            if roots != self.config['roots']:
                self.session.semantic.purge()
            self.config = new
            self.session = MiniSession(self.config)
            self.finder_artifact = None
            self.settingsChanged.emit()
            self.update(finderHits=[], finderFeedback='Đã lưu cài đặt.', status='Đã lưu cài đặt.')
            return True
        except Exception as exc:
            self.update(finderFeedback=str(exc), errorText=str(exc))
            return False

    def submit(self, operation, args, query=''):
        if self.quitting:
            return
        self.generation += 1
        self.pending = operation, args, query, self.generation
        if self.job:
            self.job.stop.set()
            self.update(status='Đang hủy tác vụ trước…')
        else:
            self.start_pending()

    def start_pending(self):
        if not self.pending:
            return
        operation, args, query, generation = self.pending
        self.pending = None
        self.update(busy=True, phase='working', view='answer', expanded=True, hasWorkbench=True,
            answerText='', answerHtml='', answerHtmlDark='', answerExcerpt='', errorText='', errorCode='',
            query=query, userQuery=query, status='Đang thực hiện…', title='Chuột đang làm', processSteps=[])
        job = MiniJob(self.session, operation, args, query, generation)
        self.job = job
        job.progress.connect(lambda text: self.update(status=text) if job.generation == self.generation else None)
        job.result.connect(lambda value: self.render(value) if job.generation == self.generation else None)
        job.finished.connect(lambda: self.finished(job))
        job.start()

    def finished(self, job):
        self.job = None
        job.deleteLater()
        if self.quitting:
            self.quitRequested.emit()
        elif self.pending:
            self.start_pending()
        else:
            self.update(busy=False)

    def render(self, value):
        self.showRequested.emit()
        response = value.get('response')
        error = value.get('error') or (response.error if response else None)
        self.update(busy=False, phase='result', expanded=True, hasWorkbench=True)
        if error:
            cancelled = str(error).startswith('cancelled')
            self.answer('Đã hủy.' if cancelled else str(error), outcome='cancelled' if cancelled else 'error')
            return
        if response.pending_input_request:
            self.answer(response.pending_input_request.prompt, outcome='needs_input')
            return
        for artifact in reversed(response.artifacts):
            data = artifact.payload
            if artifact.kind == 'finder_results':
                self.finder_artifact = artifact
                hits = [{**hit, 'kind': 'file', 'is_pdf': Path(hit['path']).suffix.lower()=='.pdf',
                         'display_path': hit['path'], 'origin': ' + '.join(hit['match_sources']),
                         'match_reason': ' + '.join(hit['match_sources'])} for hit in data['hits']]
                self.update(view='finder', finderHits=hits, title='Kết quả tìm file',
                    status=f"{len(hits)} file · {data['coverage']['roots']} thư mục · " +
                    ('Tìm kiếm có giới hạn' if data['status']=='partial' else 'Đã kiểm tra file và quyền đọc'),
                    finderFeedback=' · '.join(data.get('interpretation', [])))
                if not hits:
                    self.update(finderFeedback='Chưa tìm thấy trong phạm vi đã chọn. Kiểm tra thư mục hoặc lập chỉ mục ngữ nghĩa.')
                return
            if artifact.kind == 'translation':
                self.answer(data['text'], title=f"{data['source_language']} → {data['target_language']} · {data['provider']}",
                            outcome='completed' if data['status']=='complete' else 'partial',
                            verification=response.answer_verification_status)
                self.update(status=' · '.join(data.get('warnings', [])) or
                            'Đã dịch đoạn văn. Kiểm tra kỹ thuật không bảo chứng đúng nghĩa.')
                return
            if artifact.kind == 'index_receipt':
                self.answer(f"Đã lập chỉ mục {data['indexed_files']} file, {data['chunks']} đoạn. "
                    f"{data['skipped']} file bỏ qua. Chỉ mục cập nhật thủ công; lập lại sau khi thêm hoặc sửa file.",
                    title='Chỉ mục ngữ nghĩa', outcome='completed' if data['status']=='complete' else 'partial')
                return
        self.answer(response.answer, verification=response.answer_verification_status)

    def answer(self, text, title='RAT Mini', outcome='completed', verification='UNKNOWN'):
        markup = '<p style="white-space:pre-wrap">' + html.escape(text).replace('\n','<br>') + '</p>'
        self.update(view='answer', title=title, answerText=text, answerHtml=markup, answerHtmlDark=markup,
                    answerExcerpt=text[:220], oneLineAnswer=text[:160], answerOutcome=outcome,
                    answerVerification=verification, canCopy=bool(text), status=title)

    @pyqtSlot(bool)
    def setExpanded(self, expanded):
        self.update(expanded=expanded, unread=False)

    @pyqtSlot(str)
    def setWorkspaceMode(self, mode):
        if mode in ('minimal','single','multi'):
            self.update(workspaceMode=mode)

    @pyqtSlot()
    def cancel(self):
        self.generation += 1
        self.pending = None
        if self.job:
            self.job.stop.set()
        self.update(busy=False, phase='result', status='Đã yêu cầu hủy.', answerOutcome='cancelled')

    @pyqtSlot()
    def quit(self):
        self.quitting = True
        self.cancel()
        if not self.job:
            self.quitRequested.emit()

    @pyqtSlot(str, result=bool)
    def copyCitation(self, selected=''):
        text = selected or self.state.get('answerText', '')
        if text:
            QGuiApplication.clipboard().setText(text)
            self.copyConfirmed.emit(text)
        return bool(text)

    def file_action(self, index, operation):
        hits = self.state['finderHits']
        if self.finder_artifact and 0 <= index < len(hits):
            self.submit(operation, {'artifact_id': self.finder_artifact.id, 'revision': self.finder_artifact.revision,
                                    'resource_id': hits[index]['resource_id']})

    @pyqtSlot(int)
    def openSelectedHit(self, index):
        self.file_action(index, 'open_file')

    @pyqtSlot(int)
    def revealSelectedInFinder(self, index):
        self.file_action(index, 'reveal_file')

    @pyqtSlot(str)
    def openHit(self, path):
        index = next((i for i,h in enumerate(self.state['finderHits']) if h['path']==path), -1)
        self.file_action(index, 'open_file')

    @pyqtSlot()
    def dismissFinder(self):
        self.update(finderHits=[], view='none', hasWorkbench=False)

    @pyqtSlot()
    def clearActiveContext(self):
        self.dismissFinder()

    @pyqtSlot()
    def backToSearch(self):
        self.update(view='finder')
