"""Qt Quick projection of MiniSession; business execution stays in its tools."""
from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from rat.os.hotkey_chords import CHORDS, DEFAULT_CHORD, chord
import json
import logging
import time
import subprocess
from PyQt6.QtCore import QObject, QPoint, QTimer, QUrl, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QCursor

from rat.engine.mini_settings import read_settings, save_settings, keychain_key, state_directory
from rat.mini import MiniSession
from rat.ui.mini_worker import MiniJob
from rat.ui.mini_diagnostics import BUILD, write_diagnostic
from rat.ui.quick_look_journal import QuickLookJournal
from rat.ui.mini_presentation import MiniPresentation
from rat.ui.image_input import IMAGE_SUFFIXES, ENCODED_IMAGE_TYPES, image_from_mime, image_from_url
from rat.ui.image_preview import ImagePreviewProvider
from rat.os.permissions import runtime_identity


class MiniQuickController(QObject):
    changed = pyqtSignal()
    presentRequested = pyqtSignal()
    engagementRequested = pyqtSignal()
    helpRequested = pyqtSignal()
    hideRequested = pyqtSignal()
    settingsRequested = pyqtSignal()
    regionCaptureRequested = pyqtSignal()
    lookRequested = pyqtSignal()
    minimalRequested = pyqtSignal()
    lookFocusRequested = pyqtSignal()
    lookResultDismissed = pyqtSignal()
    hotkeyRestartRequested = pyqtSignal()
    shortcutAcknowledged = pyqtSignal(str)
    selectionAnchorRequested = pyqtSignal(object)
    restoreAnchorRequested = pyqtSignal(int)
    presentAtRequested = pyqtSignal(QPoint)
    imageDropAccepted = pyqtSignal(str)
    interactionCompleted = pyqtSignal()

    def __init__(self, settings=None):
        super().__init__()
        self.settings = dict(settings if settings is not None else read_settings())
        self.session = MiniSession(self.settings)
        self.job = self.pending = self.finder_artifact = None
        self.organization_artifact = None
        self.presentation = MiniPresentation(surface="result" if self.settings.get("setup_completed") and self.settings.get("permission_hello_version", 0) >= 1 else "welcome")
        self._task_history = []
        self.rebind_hotkey = None
        self._next_draft = ""
        self.generation = 0
        self.quitting = False
        self._paste_hint = None
        self._draft_image = None
        self._capture_position = None
        self._result_ref = None
        self._ocr_source_ref = None
        self._ocr_current_text = ''
        self._translation_args = None
        self._receiving_token = None
        self.image_preview = ImagePreviewProvider()
        self._last_image = None
        self._image_instruction = ''
        self._retry_request = None
        self._region_previous = None
        self._selection_present_generation = None
        self._selection_return = None
        self._received_invocation_id = None
        self._selection_invocation_id = None
        self._selection_invoked_at = 0.0
        self._presentation_invocation_id = None
        self.quicklook_journal = QuickLookJournal(state_directory(), BUILD)
        self.regionCaptureRequested.connect(self.captureRegion, Qt.ConnectionType.QueuedConnection)
        self._state = dict(draftText='', editingRequest=False, settingsNotice='', lastOperation='', organizationGroups=[], readinessSummary=[], agentSummary='', agentIncomplete=False, lookSource=False, hotkeyStatus='', sameLanguageNotice='',
            phase='idle', busy=False, bubbleCollapsed=False, expanded=False, selectionNotice='', selectionNeedsPermission=False, captureSourceApp='', captureSourceKind='', hotkeyStarting=False, shortcutAck='', pinned=False,
            hasWorkbench=False, view='idle', finderHits=[], text='', meta='', canReturnToFinder=False,
            status='Bạn muốn Chuột giúp gì?', requestText='', attachmentLabel='', error=False,
            ocrText='', ocrOriginalText='', ocrCommittedText='', hasOcrSource=False, canRetryTranslation=False,
            translationDetails='', translationNotice='', translationSettingsSuggested=False,
            dropActive=False, receivingImage=False, imagePreviewUrl='', imageLabel='',
            ocrPreparationNotice='', canRetryRequest=False, finderSettingsSuggested=False,
            imageInputSuggested=False, organization={}, organizationRows=[], canApplyOrganization=False, canUndoOrganization=False,
            organizationRecoverySuggested=False, setupCompleted=bool(self.settings.get("setup_completed", False) and self.settings.get('permission_hello_version',0) >= 1), readiness=[], readinessBusy=False, readinessStatus="")
        self.shortcut_ack_timer = QTimer(self)
        self.shortcut_ack_timer.setSingleShot(True)
        self.shortcut_ack_timer.timeout.connect(lambda: self.update(shortcutAck=''))
        self.record_ui_state()
        if self.presentation.surface == 'welcome':
            QTimer.singleShot(0, lambda: self.checkReadiness(False))

    @pyqtProperty('QVariantMap', notify=changed)
    def snapshot(self):
        state = dict(self._state, **self.presentation.snapshot())
        return dict(state,
            lookStatusLabel='Đang xử lý' if self._state['busy'] else 'Sẵn sàng',
            runningBundlePath=runtime_identity().get('bundle_path') or '',
            accessibilityReady=any(c.get('key') == 'accessibility' and c.get('state') in ('ready','not_required') for c in self._state['readiness']),
            shortcutLabel=chord(self.settings.get('hotkey_chord', DEFAULT_CHORD))[2],
            taskHistory=[dict(index=i, title=item['title']) for i,item in enumerate(self._task_history)],
            diagnosticEvents=self.diagnostic_events(),
            ocrDirty=bool(self._state["hasOcrSource"]) and self._state["ocrText"] != self._state["ocrCommittedText"])

    @pyqtProperty('QVariantMap', notify=changed)
    def preferences(self):
        return dict(self.settings)

    def record_ui_state(self):
        write_diagnostic('ui-state.json', dict(surface=self.presentation.surface,
            extent=self.presentation.extent, composer_visible=self.presentation.composer_visible,
            busy=self._state['busy'], phase=self._state['phase'],
            has_result=self._state['hasWorkbench'], operation=self._state['lastOperation'],
            task_id=self.presentation.task_id, generation=self.generation))

    def update(self, **values):
        self._state.update(values)
        self.record_ui_state()
        self.changed.emit()

    @pyqtSlot()
    def summonLook(self):
        if not self._state['setupCompleted']:
            self.presentation.open('welcome')
            self.update()
            self.presentRequested.emit()
            return
        if self._state['selectionNotice']:
            self.recallLookResult()
            return
        self._state['selectionNotice'] = ''
        self.presentation.open('result')
        self.presentation.read()
        self.update()
        self.lookRequested.emit()

    @pyqtSlot()
    def dismissLookResult(self):
        if self._selection_invocation_id:
            self.quicklook_journal.record('dismissed', invocation_id=self._selection_invocation_id)
        self._selection_present_generation = None
        self._presentation_invocation_id = None
        self.update()
        self.lookResultDismissed.emit()

    @pyqtSlot()
    def recallLookResult(self):
        if self._state['selectionNotice']:
            self.returnToTask()
            self.lookRequested.emit()
            return
        self._state['selectionNotice'] = ''
        self.presentation.open('result')
        self.presentation.read() if self._state['hasWorkbench'] else self.presentation.compose()
        self.update()
        self.lookRequested.emit()

    @pyqtSlot()
    def returnToTask(self):
        if self._state['selectionNotice']:
            if self._selection_return is not None:
                self.restore_selection_view()
            elif self._state['hasWorkbench']:
                self.presentation.read()
            else:
                self.presentation.compose()
            self.update(selectionNotice='', selectionNeedsPermission=False)
            return
        self.update()

    @pyqtSlot()
    def summonMinimal(self):
        if not self._state['setupCompleted']:
            self.presentation.open('welcome')
            self.update()
            self.presentRequested.emit()
            return
        if self._state['selectionNotice']:
            self.returnToTask()
        self._state['selectionNotice'] = ''
        self.presentation.open('result')
        self.presentation.compose()
        self.update()
        self.minimalRequested.emit()

    @pyqtSlot()
    def focusLook(self):
        self.update()
        self.lookFocusRequested.emit()

    @pyqtSlot()
    def pasteSelectionFallback(self):
        if self.job or self._state['busy']:
            return
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            self.update(selectionNotice='Clipboard chưa có chữ. Hãy chọn và copy đoạn trong app nguồn, rồi bấm Dán chữ.')
            return
        self._selection_return = None
        self.presentation.open('result')
        self.presentation.resize(False)
        self.presentation.read()
        self.update(selectionNotice='', selectionNeedsPermission=False, requestText='Dịch đoạn vừa dán')
        self.enqueue('capture_translate', dict(mode='clipboard', clipboard_text=text, look_input=True,
            source_language=self.settings['source_language'], target_language=self.settings['target_language']))

    @pyqtSlot()
    def pasteLook(self):
        """Explicit paste only; never consume the hidden composer's draft."""
        if self._state['busy'] or self.quitting:
            return
        value = self.pasteInput('')
        if value.get('text') and value.get('kind') == 'pasted_text':
            self.clearAttachment()
            self.clearImagePreview()
            self.presentation.open('result')
            self.presentation.resize(False)
            self.presentation.read()
            self.update(requestText='Dịch đoạn vừa dán')
            self.enqueue('capture_translate', dict(mode='clipboard', clipboard_text=value['text'],
                look_input=True,
                source_language=self.settings['source_language'],
                target_language=self.settings['target_language']))

    @pyqtSlot(str)
    def showSurface(self, surface):
        if surface in ('ocr', 'source') and not self._state['hasOcrSource']:
            return
        if surface == 'image':
            if not self._state['imagePreviewUrl']:
                return
            self.presentation.inspect_image()
        else:
            self.presentation.open(surface)
        if surface in self.presentation.WORKSPACE:
            if surface != 'result':
                self.presentation.resize(True)
            self._state['expanded'] = True
        self.changed.emit()

    @pyqtSlot()
    def backSurface(self):
        if not self._state['setupCompleted']:
            self.presentation.open('welcome')
        else:
            self.presentation.back()
        self.changed.emit()

    @pyqtSlot(float)
    def rememberScroll(self, offset):
        self.presentation.scroll[self.presentation.scroll_key] = max(0.0, float(offset))

    @pyqtSlot(int, int)
    def rememberLookSelection(self, start, end):
        if not self._state['busy']:
            self.presentation.selections[self.presentation.task_id] = max(0, start), max(0, end)

    @pyqtSlot(str, int, float)
    def rememberReadingAnchor(self, text, position, delta):
        if not self._state['busy']:
            length = len(text.encode('utf-16-le')) // 2
            self.presentation.reading_anchor = (text, max(0, min(position, length)), float(delta))

    @pyqtSlot()
    def toggleSource(self):
        self.presentation.source_visible = not self.presentation.source_visible
        self.presentation.resize(True)
        self.update(expanded=True)

    @pyqtSlot(str)
    def copyLookSelection(self, text):
        if text:
            QGuiApplication.clipboard().setText(text)

    @pyqtSlot(str)
    def setComposerDraft(self, text):
        if text != self._state['draftText']:
            self.update(draftText=text)

    def consume_submission(self, submitted):
        if self._state['editingRequest']:
            self.update(editingRequest=False, draftText=self._next_draft)
            self._next_draft = ''
        elif self._state['draftText'].strip() == submitted.strip():
            self.update(draftText='')

    @pyqtSlot()
    def submitDraft(self):
        if not self._state['busy']:
            self.submit(self._state['draftText'])

    @pyqtSlot()
    def cancelEditRequest(self):
        if self._state['editingRequest']:
            self.clearAttachment()
            self.update(draftText=self._next_draft, editingRequest=False)
            self._next_draft = ''

    def complete_surface(self):
        self.presentation.complete()

    @pyqtSlot(bool)
    def checkReadiness(self, deep=False):
        if self.job or self.pending:
            self.update(readinessStatus='Đợi tác vụ hiện tại kết thúc rồi kiểm tra nhé.')
            return
        self.update(readinessBusy=True, readinessStatus='Đang kiểm tra thành phần trên máy…')
        self.enqueue('check_mini_readiness', {'deep':deep})

    @pyqtSlot(result=str)
    def completeSetup(self):
        try:
            updated = dict(self.settings, setup_completed=True, permission_hello_version=1)
            save_settings(updated)
            self.settings = updated
            self.presentation.back()
            self.presentation.compose()
            self.update(setupCompleted=True)
            return ''
        except OSError:
            return 'Chưa lưu được thiết lập. Bạn vẫn có thể đóng cửa sổ để dùng RAT.'

    @pyqtSlot(QUrl)
    def organizeFolder(self, url):
        path = self.localFolderPath(url)
        if not path:
            return
        self.clearImagePreview()
        self.update(requestText='Sắp xếp ' + path)
        self.enqueue('plan_folder_organization', {'folder':path, 'rule':'type'})

    @pyqtSlot()
    def applyOrganization(self):
        self._approved_organization('apply_folder_organization', 'organization_plan')

    @pyqtSlot()
    def undoOrganization(self):
        self._approved_organization('undo_folder_organization', 'organization_receipt')

    def _approved_organization(self, operation, kind):
        artifact = self.organization_artifact
        if self.job or self._state['view'] != 'organization' or not artifact or artifact.kind != kind:
            return
        pin = {'artifact_id':artifact.id, 'revision':artifact.revision}
        self.update(canApplyOrganization=False, canUndoOrganization=False)
        self.enqueue(operation, pin, input_context={'organization_approval':dict(pin)})

    @pyqtSlot()
    def recoverOrganization(self):
        if not self.job:
            self.enqueue('get_last_organization', {})

    @pyqtSlot(bool)
    def setExpanded(self, value):
        self.presentation.resize(value)
        if not value:
            self.presentation.open('result')
        self.update(expanded=value)

    @pyqtSlot(str)
    def submit(self, text):
        if self.quitting or self._state['busy']:
            return
        text = text.strip()
        if self._draft_image is not None:
            image = self._draft_image
            self.clearAttachment()
            if self._state['hasOcrSource'] and self._state['canRetryTranslation'] and self._translation_args:
                # Editing the request must not discard corrected OCR or run it
                # again. Language routing stays in the shared orchestration.
                self.consume_submission(text)
                self.presentation.open('result')
                self._image_instruction = text
                self.update(requestText=text or f"Dịch ảnh: {self._state['imageLabel']}")
                if self._state['ocrText'] == self._ocr_current_text:
                    self.enqueue('translate_text', dict(self._translation_args), text)
                else:
                    self.enqueue('correct_translate', {'source_ref':dict(self._ocr_source_ref),
                        'text':self._state['ocrText'], 'translation_args':dict(self._translation_args)}, text)
                return
            self.acceptDroppedImage(image, self._state['imageLabel'] or 'Ảnh đã nhận', text)
            return
        if not text:
            self.update(status='Nhập tên file hoặc đoạn cần dịch trước nhé.')
            return
        if self.presentation.surface == 'ocr' and self._ocr_source_ref:
            self.consume_submission(text)
            self.update(requestText=text)
            if self._state['ocrText'] != self._ocr_current_text:
                self.enqueue('correct_translate', {'source_ref': dict(self._ocr_source_ref),
                    'text': self._state['ocrText'], 'translation_args': dict(self._translation_args)}, text)
            else:
                self.enqueue('submit_goal', {'input_kind': 'typed',
                    'source_ref': dict(self._ocr_source_ref), 'result_ref':dict(self._result_ref) if self._result_ref else None}, text)
            return
        self.clear_ocr_source()
        # A new text request must not display a thumbnail from a previous task.
        self.clearImagePreview()
        self.consume_submission(text)
        self.update(requestText=text)
        input_kind = self._paste_hint[1] if self._paste_hint and self._paste_hint[0] == text else 'typed'
        self._paste_hint = None
        self.enqueue('submit_goal', {'input_kind':input_kind, 'result_ref':dict(self._result_ref) if self._result_ref else None}, text)

    @pyqtSlot(result='QVariantMap')
    @pyqtSlot(str, result='QVariantMap')
    def pasteInput(self, instruction=''):
        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is None:
            return {'text':'', 'kind':'typed'}
        local_urls = [u for u in mime.urls() if u.isLocalFile()] if mime.hasUrls() else []
        paths = [u.toLocalFile() for u in local_urls]
        if paths:
            if len(paths) == 1 and Path(paths[0]).suffix.lower() in IMAGE_SUFFIXES:
                try:
                    image, name = image_from_mime(mime, clipboard=True)
                    self.acceptDroppedImage(image, name, instruction)
                    return {'text':'', 'kind':'image'}
                except ValueError as exc:
                    self.image_input_error(str(exc))
                    return {'text':'', 'kind':'none'}
            self.clearAttachment()
            return {'text':'\n'.join(paths), 'kind':'file_reference'}
        if mime.hasImage() or any(mime.hasFormat(kind) for kind in ENCODED_IMAGE_TYPES):
            try:
                image, _ = image_from_mime(mime, clipboard=True)
            except ValueError as exc:
                self.image_input_error(str(exc))
                return {'text':'', 'kind':'none'}
            self.acceptDroppedImage(image, 'Ảnh vừa dán', instruction)
            return {'text':'', 'kind':'image'}
        return {'text':clipboard.text(), 'kind':'pasted_text'}

    def image_input_error(self, message):
        self.update(status=message, phase='error', error=True,
            hasWorkbench=True, expanded=True, imageInputSuggested=True, canRetryRequest=False,
            finderSettingsSuggested=False, translationSettingsSuggested=False)

    def setDropActive(self, value):
        if self._state['dropActive'] != value:
            self.update(dropActive=value)

    def beginImageReceive(self):
        if self.quitting:
            return None
        self.presentation.begin_task()
        self.generation += 1
        self._receiving_token = self.generation
        self.pending = None
        if self.job:
            self.job.stop.set()
        self.clearAttachment()
        self.clearImagePreview()
        self.clear_ocr_source()
        self.update(receivingImage=True, busy=True, phase='working', view='notice', error=False,
            text='', meta='', expanded=True, hasWorkbench=True, requestText='Dịch ảnh đang nhận',
            imageInputSuggested=False, finderSettingsSuggested=False, translationSettingsSuggested=False,
            canRetryRequest=False, status='Đang nhận ảnh từ macOS…')
        return self._receiving_token

    def isImageReceiveCurrent(self, token):
        return not self.quitting and token == self._receiving_token and token == self.generation

    def finishImageReceive(self, token, *, image=None, label='', instruction='', error=None):
        if not self.isImageReceiveCurrent(token):
            return False
        self._receiving_token = None
        self.update(receivingImage=False, busy=self.job is not None)
        if error:
            self.image_input_error(error)
            return False
        return self.acceptDroppedImage(image, label, instruction)

    @pyqtSlot('QVariantList', str, result=bool)
    def dropImage(self, urls, instruction=''):
        if self.quitting:
            return False
        if len(urls) != 1:
            self.image_input_error('Hãy thả từng ảnh một để RAT dịch.')
            return False
        try:
            image, name = image_from_url(urls[0])
        except ValueError as exc:
            self.image_input_error(str(exc))
            return False
        return self.acceptDroppedImage(image, name, instruction)

    @pyqtSlot(QUrl, str, result=bool)
    def chooseImageFile(self, url, instruction=''):
        """Explicit picker input, normalized into the same shared tool workflow."""
        if self.quitting:
            return False
        try:
            image, name = image_from_url(url, origin='selected_file')
        except ValueError as exc:
            self.image_input_error(str(exc))
            return False
        return self.acceptDroppedImage(image, name, instruction)

    def acceptDroppedImage(self, image, label, instruction=''):
        if self.quitting:
            return False
        self.clearAttachment()
        self.clear_ocr_source()
        self._paste_hint = None
        self._last_image, self._image_instruction = image, instruction.strip()
        preview = self.image_preview.set_input(image)
        self.update(requestText=instruction.strip() or f'Dịch ảnh: {label}',
            imagePreviewUrl=preview, imageLabel=label, imageInputSuggested=False)
        if instruction.strip():
            self.consume_submission(instruction)
        self.enqueue('capture_translate', dict(mode='image', image_input=image,
            look_input=True,
            source_language=self.settings['source_language'],
            target_language=self.settings['target_language']), instruction.strip())
        self.imageDropAccepted.emit(instruction)
        return True

    @pyqtSlot(str, str)
    def rememberPaste(self, text, kind):
        self._paste_hint = (text.strip(),kind)

    @pyqtSlot()
    def clearAttachment(self):
        self._draft_image = None
        self.update(attachmentLabel='')

    def clearImagePreview(self):
        self._last_image, self._image_instruction = None, ''
        self.image_preview.clear()
        self.update(imagePreviewUrl='', imageLabel='', ocrPreparationNotice='')

    @pyqtSlot(result=str)
    def editRequest(self):
        if self._state['busy']:
            return ''
        if not self._state['editingRequest']:
            self._next_draft = self._state['draftText']
        text = self._image_instruction if self._last_image is not None else self._state['requestText']
        if self._last_image is not None:
            self._draft_image = self._last_image
        self.update(draftText=text, editingRequest=True,
            attachmentLabel=(self._state['imageLabel'] + ' · ảnh được giữ') if self._last_image is not None else '')
        return text

    @pyqtSlot()
    def retryRequest(self):
        if self._state['busy'] or self._state['imageInputSuggested'] or not self._state['canRetryRequest']:
            return
        if self._state['hasOcrSource'] and self._state['canRetryTranslation']:
            self.retryTranslation(self._state['ocrText'])
        elif self._retry_request:
            operation, arguments, query = self._retry_request
            if operation == 'capture_translate' and arguments.get('mode') == 'region':
                self.captureRegion()
                return
            self.enqueue(operation, dict(arguments), query)

    @pyqtSlot(QUrl, result=str)
    def localFolderPath(self, url):
        # Native dialogs deliver QUrl. Do not manually URL-decode paths in QML.
        return url.toLocalFile() if url.isLocalFile() and url.host() in ('', 'localhost') else ''

    def clear_ocr_source(self):
        self._ocr_source_ref = self._translation_args = None
        self._ocr_current_text = ''
        if self.presentation.workspace in ('ocr','source','image'):
            self.presentation.workspace = 'result'
        if self.presentation.surface in ('ocr','source'):
            self.presentation.surface = 'result'
        self.update(ocrText='', ocrOriginalText='', ocrCommittedText='', hasOcrSource=False, canRetryTranslation=False, lookSource=False, captureSourceKind='')

    @pyqtSlot(str)
    def setOcrDraft(self, text):
        if self._state['hasOcrSource'] and not self._state['busy'] and text != self._state['ocrText']:
            self.update(ocrText=text)

    @pyqtSlot(str)
    def retryTranslation(self, text):
        if self.quitting or self._state['busy'] or not self._ocr_source_ref or not self._translation_args:
            return
        if not text.strip() or len(text) > 8000:
            self.update(phase='error', status='Chữ cần dịch phải có từ 1 đến 8.000 ký tự.', error=True)
            return
        self.presentation.open('result')
        self.update(ocrText=text)
        if text == self._ocr_current_text:
            self.enqueue('translate_text', dict(self._translation_args))
        else:
            self.enqueue('correct_translate', {'source_ref':dict(self._ocr_source_ref),
                'text':text, 'translation_args':dict(self._translation_args)})

    @pyqtSlot()
    def captureRegion(self):
        logging.getLogger(__name__).info('region_capture_requested')
        if self.quitting:
            return
        if self.job or self.pending or self._state['busy'] or self._region_previous:
            self.update(status='Đợi tác vụ hiện tại hoàn tất.')
            return
        fields = ('phase', 'status', 'error', 'expanded', 'hasWorkbench', 'view',
            'agentSummary', 'agentIncomplete', 'settingsNotice', 'lastOperation',
            'translationSettingsSuggested', 'finderSettingsSuggested', 'imageInputSuggested',
            'organizationRecoverySuggested', 'canRetryRequest')
        self._region_previous = ({key: self._state[key] for key in fields}, self._retry_request)
        self.presentation.open('result')
        self.presentation.resize(False)
        self.presentation.read()
        # Reserve a generation now, so cancel/new input invalidates the deferred capture.
        self.generation += 1
        generation = self.generation
        self._capture_position = None

        def begin():
            if self.quitting or generation != self.generation:
                return
            logging.getLogger(__name__).info('region_capture_dispatching')
            self.enqueue('capture_translate', dict(mode='region', source_language=self.settings['source_language'],
                target_language=self.settings['target_language'], preserve_until_capture=True,
                look_input=True))
        QTimer.singleShot(160, begin)

    @pyqtSlot()
    def quickLookSelection(self):
        """Pin the source before showing/activating RAT; capture runs in its tool."""
        invocation = self._received_invocation_id or self.quicklook_journal.invocation_id()
        self._received_invocation_id = None
        self.quicklook_journal.record('invoked', invocation_id=invocation)
        if not self._state['setupCompleted']:
            self.quicklook_journal.record('setup_required', invocation_id=invocation)
            self.summonLook()
            return
        if self.quitting:
            self.quicklook_journal.record('ignored_shutdown', invocation_id=invocation)
            return
        if self.job or self.pending or self._region_previous:
            self.quicklook_journal.record('ignored_busy', invocation_id=invocation)
            message = 'RAT đang xử lý yêu cầu trước. Nội dung hiện tại được giữ; bạn bấm lại khi xong nhé.'
            self.update(shortcutAck=message)
            self.shortcut_ack_timer.start(4000)
            self.shortcutAcknowledged.emit(message)
            return
        self.update(bubbleCollapsed=False)
        self._selection_invocation_id = invocation
        self._selection_invoked_at = time.monotonic()
        try:
            self._begin_selected_text(invocation)
        except Exception as exc:
            self.quicklook_journal.record('callback_error', invocation_id=invocation, reason=type(exc).__name__)
            if self._selection_return is None:
                self._selection_return = self.presentation.capture_view()
            self.restore_region_previous()
            self.presentation.resize(False)
            self.presentation.read()
            self.update(selectionNotice='Chưa nhận được vùng chọn. Mã QL_CALLBACK_FAILED. Bạn có thể quay lại công việc trước.',
                selectionNeedsPermission=False)
            self._presentation_invocation_id = invocation
            self.quicklook_journal.record('present_requested', invocation_id=invocation)
            self.lookRequested.emit()

    def recordHotkeyState(self, stage, **metadata):
        invocation = None
        if stage == 'selection':
            self._received_invocation_id = self.quicklook_journal.invocation_id()
            invocation = self._received_invocation_id
        self.quicklook_journal.record(stage, invocation_id=invocation, **metadata)

    def selectionPresented(self):
        if self._presentation_invocation_id:
            self.quicklook_journal.record('presented', invocation_id=self._presentation_invocation_id)
            self._presentation_invocation_id = None

    def restore_selection_view(self):
        if self._selection_return is not None:
            token = self._selection_return
            self._selection_return = None
            self.presentation.restore_view(token)

    def _begin_selected_text(self, invocation):
        import os
        import sys
        if sys.platform != 'darwin':
            self.quicklook_journal.record('unsupported_platform', invocation_id=invocation)
            self.summonLook()
            return
        from AppKit import NSWorkspace
        source = NSWorkspace.sharedWorkspace().frontmostApplication()
        if source is None or int(source.processIdentifier()) == os.getpid():
            self.quicklook_journal.record('recall_own_app', invocation_id=invocation)
            self.summonLook()
            return
        if self._selection_return is None:
            self._selection_return = self.presentation.capture_view()
        fields = ('phase', 'status', 'error', 'expanded', 'hasWorkbench', 'view',
            'agentSummary', 'agentIncomplete', 'settingsNotice', 'lastOperation',
            'translationSettingsSuggested', 'finderSettingsSuggested', 'imageInputSuggested',
            'organizationRecoverySuggested', 'canRetryRequest')
        self._region_previous = ({key: self._state[key] for key in fields}, self._retry_request)
        self.presentation.open('result')
        self.presentation.resize(False)
        self.presentation.read()
        self.update(selectionNotice='', selectionNeedsPermission=False)
        self.enqueue('capture_translate', dict(mode='selection', preserve_until_capture=True,
            look_input=True, source_language=self.settings['source_language'],
            target_language=self.settings['target_language']),
            input_context={'selection_pid': int(source.processIdentifier()), 'selection_app': str(source.localizedName() or ''), 'quicklook_invocation_id':invocation})
        self._selection_present_generation = self.generation
        self.quicklook_journal.record('capture_requested', invocation_id=invocation, generation=self.generation)
        # No present signal here: AX must read the source before RAT can take focus.

    @pyqtSlot()
    def revealRunningApp(self):
        path = runtime_identity().get('bundle_path')
        if not path:
            self.update(readinessStatus='Bản source chưa có app bundle để chọn.')
            return
        try:
            subprocess.Popen(['open', '-R', path])
        except OSError:
            self.update(readinessStatus='Chưa mở được Finder. Đường dẫn app được hiển thị bên dưới.')

    @pyqtSlot()
    def openSelectionAccess(self):
        from rat.os.permissions import open_accessibility_settings
        self.quicklook_journal.record('permission_settings_requested', invocation_id=self._selection_invocation_id)
        if not open_accessibility_settings():
            self.update(selectionNotice='Chưa mở được Cài đặt. Bạn vào Quyền riêng tư & Bảo mật → Trợ năng để cho phép RAT, rồi bôi đen và bấm lại phím tắt.',
                selectionNeedsPermission=True)

    @pyqtSlot()
    def restartHotkey(self):
        self.hotkeyRestartRequested.emit()

    HISTORY_FIELDS = ('view', 'phase', 'status', 'error', 'text', 'meta', 'requestText',
        'hasWorkbench', 'pinned', 'attachmentLabel', 'finderHits', 'hasOcrSource', 'ocrText', 'ocrCommittedText', 'ocrOriginalText',
        'ocrPreparationNotice', 'captureSourceKind', 'captureSourceApp', 'lookSource', 'translationDetails', 'translationNotice',
        'sameLanguageNotice', 'organization', 'organizationRows', 'organizationGroups',
        'agentSummary', 'agentIncomplete', 'lastOperation')

    def remember_task(self):
        values = dict(self._state)
        if self._region_previous:
            values.update(self._region_previous[0])
        if not values.get('hasWorkbench') or values.get('phase') not in ('result', 'partial', 'error'):
            return
        key = self.presentation.task_id
        self._task_history = [x for x in self._task_history if x['task_id'] != key]
        fields = ('task_id', 'surface', 'workspace', 'extent', 'composer_visible', 'source_visible',
                  'scroll', 'selections', 'reading_anchor')
        view = deepcopy({k:getattr(self.presentation,k) for k in fields})
        if self._selection_return and self._selection_return[0] == key:
            view.update(self._selection_return[1])
        self._task_history.insert(0, dict(task_id=key,
            title=(values.get('requestText') or values.get('status') or 'Công việc')[:60],
            state=deepcopy({k:values[k] for k in self.HISTORY_FIELDS}),
            presentation=view, last_image=self._last_image, draft_image=self._draft_image,
            image_label=values.get('imageLabel',''),
            result_ref=deepcopy(self._result_ref), source_ref=deepcopy(self._ocr_source_ref), source_text=self._ocr_current_text,
            translation_args=deepcopy(self._translation_args), finder=self.finder_artifact,
            draft=self._next_draft))
        del self._task_history[5:]

    @pyqtSlot(int)
    def restoreTask(self, index):
        if self.job or self.pending or self._state['busy'] or not 0 <= index < len(self._task_history):
            return
        item = self._task_history.pop(index)
        self.remember_task()
        self.session = MiniSession(self.settings, artifact_store=self.session.runtime.artifact_store)
        for name,value in deepcopy(item['presentation']).items():
            setattr(self.presentation,name,value)
        self._result_ref = deepcopy(item['result_ref'])
        self._ocr_source_ref = deepcopy(item['source_ref'])
        self._ocr_current_text = item['source_text']
        self._translation_args = deepcopy(item['translation_args'])
        self.finder_artifact = item['finder']
        self.organization_artifact = None
        self._retry_request = self._region_previous = self._selection_return = None
        self._selection_present_generation = self._presentation_invocation_id = None
        self._next_draft = item['draft']
        self._last_image, self._draft_image = item['last_image'], item['draft_image']
        preview = self.image_preview.set_input(self._last_image) if self._last_image is not None else ''
        self.presentation.open('result')
        self.presentation.read()
        self.update(**item['state'], draftText=self._next_draft, busy=False,
            imagePreviewUrl=preview, imageLabel=item['image_label'], selectionNotice='', canRetryRequest=False,
            canRetryTranslation=bool(item['source_ref'] and item['translation_args']),
            canApplyOrganization=False, canUndoOrganization=False,
            organizationRecoverySuggested=item['state']['view']=='organization')
        self.restoreAnchorRequested.emit(self.presentation.task_id)
        self.lookRequested.emit()

    @pyqtSlot()
    def clearTaskHistory(self):
        self._task_history.clear()
        self.update()

    def diagnostic_events(self):
        labels = {'ready':'Phím tắt đã đăng ký', 'selection':'Đã nhận phím tắt',
            'invoked':'Đã nhận yêu cầu', 'capture_requested':'Đang lấy chữ',
            'capture_succeeded':'Đã lấy được chữ', 'capture_failed':'Chưa lấy được chữ',
            'translation_failed':'Chưa xử lý được đoạn chữ', 'execution_completed':'Đã xử lý',
            'present_requested':'Đã yêu cầu hiển thị', 'presented':'Đã hiển thị',
            'space_changed':'Space đã đổi trong lúc gọi', 'space_policy_failed':'Không đặt được cửa sổ trên Space hiện tại',
            'registration_failed':'Đăng ký phím thất bại', 'ignored_busy':'Đang bận', 'dismissed':'Đã ẩn'}
        with self.quicklook_journal.lock:
            return [dict(stage=e['stage'], label=labels.get(e['stage'],e['stage']), sequence=e['sequence'])
                    for e in list(self.quicklook_journal.events)[-12:]]

    @pyqtSlot(str)
    def reportDiagnosticError(self, message):
        self.update(settingsNotice=message)

    @pyqtSlot(str, result=str)
    def exportDiagnostics(self, url):
        path = QUrl(url).toLocalFile()
        if not path:
            return 'Hãy chọn một file trên máy.'
        try:
            with self.quicklook_journal.lock:
                payload = dict(build=BUILD, protocol='SELECT2',
                    helper_state=self.quicklook_journal.helper_state, events=list(self.quicklook_journal.events))
            # Explicit export contains the journal whitelist only: no source,
            # text, paths, screenshots, geometry or settings/credentials.
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            self.update(settingsNotice='Đã xuất chẩn đoán; không kèm nội dung nguồn.')
            return ''
        except OSError:
            return 'Chưa ghi được file chẩn đoán ở vị trí này.'

    @pyqtSlot(str, result=str)
    def changeShortcut(self, name):
        if self.job or not self.rebind_hotkey:
            return 'Đợi tác vụ kết thúc trước khi đổi phím tắt.'
        try:
            chord(name)
            old = self.settings.get('hotkey_chord', DEFAULT_CHORD)
            error = self.rebind_hotkey(name)
            if error:
                return error
            try:
                updated = {**self.settings, 'hotkey_chord': name}
                save_settings(updated)
            except Exception:
                rollback_error = self.rebind_hotkey(old)
                return 'Chưa lưu được phím mới. ' + (rollback_error or 'Đã khôi phục phím cũ.')
            self.settings = updated
            self.update()
            return ''
        except ValueError:
            return 'Tổ hợp phím chưa được hỗ trợ.'



    @pyqtSlot()
    def togglePin(self):
        self.update(pinned=not self._state['pinned'])

    @pyqtSlot()
    def collapseBubble(self):
        self._selection_present_generation = None
        self._presentation_invocation_id = None
        self.presentation.read()
        self.update(bubbleCollapsed=True)

    @pyqtSlot()
    def toggleComposer(self):
        if self._state['bubbleCollapsed']:
            self.update(bubbleCollapsed=False)
            if self._state['hasWorkbench']:
                return
        self.presentation.composer_visible = not self.presentation.composer_visible
        self.update()
        if self.presentation.composer_visible:
            self.minimalRequested.emit()

    def restore_region_previous(self):
        if self._region_previous is not None:
            values, self._retry_request = self._region_previous
            self._region_previous = None
            self.update(**values)

    @pyqtSlot()
    def translateClipboard(self):
        self.clearAttachment()
        self.clearImagePreview()
        self._paste_hint = None
        # Snapshot on the GUI thread. Capture and translation still use tool contracts.
        text = QGuiApplication.clipboard().text()
        self.update(requestText=text or 'Dịch Clipboard')
        self.enqueue('capture_translate', dict(mode='clipboard', clipboard_text=text, look_input=True,
            source_language=self.settings['source_language'],
            target_language=self.settings['target_language']))

    def enqueue(self, operation, args, query='', *, input_context=None):
        if self.quitting:
            return
        if self._region_previous is not None and not (operation == 'capture_translate' and args.get('preserve_until_capture')):
            self.restore_region_previous()
        if operation not in ('check_mini_readiness', 'open_file', 'reveal_file'):
            self._retry_request = None
            self.update(canRetryRequest=False)
        if operation in ('submit_goal', 'find_files', 'translate_text', 'capture_translate', 'correct_translate'):
            self._retry_request = operation, dict(args), query
            self.update(canRetryRequest=True)
        self.generation += 1
        self._receiving_token = None
        if self._state['receivingImage']:
            self.update(receivingImage=False)
        if operation != "check_mini_readiness":
            self.update(settingsNotice='', organizationRecoverySuggested=operation in ("apply_folder_organization", "undo_folder_organization"))
        self.update(bubbleCollapsed=False)
        self.pending = operation, args, query, self.generation, input_context
        if self.job:
            self.job.stop.set()
            self.update(status='Đang dừng tác vụ trước…')
        else:
            self.start_pending()

    def start_pending(self):
        operation, args, query, generation, input_context = self.pending
        self.pending = None
        new_task = (operation in ('find_files', 'capture_translate', 'plan_folder_organization', 'get_last_organization')
                    or (operation == 'submit_goal' and self._state['phase'] != 'needs_input' and not args.get('source_ref'))
                    or (operation == 'translate_text' and not args.get('source_ref')))
        preserve_region = operation == 'capture_translate' and args.get('mode') in ('region', 'selection') and args.get('preserve_until_capture')
        if new_task and not preserve_region:
            self.remember_task()
            self._selection_return = None
            self._selection_invocation_id = None
            self._presentation_invocation_id = None
            self._state['selectionNotice'] = ''
            self.presentation.begin_task()
            self._result_ref = None
        if not preserve_region and (operation in ('find_files', 'capture_translate')
                or (operation == 'submit_goal' and not args.get('source_ref') and self._state['phase'] != 'needs_input')
                or (operation == 'translate_text' and not args.get('source_ref'))):
            self.clear_ocr_source()
        is_file_translate = (operation == 'capture_translate' and args.get('mode') == 'file')
        if new_task and not preserve_region:
            if not is_file_translate:
                self.finder_artifact = None
            self.organization_artifact = None
            self.update(pinned=False, canApplyOrganization=False, canUndoOrganization=False, canReturnToFinder=False)
            self.update(view='notice', finderHits=[], text='', meta='', translationDetails='', translationNotice='', sameLanguageNotice='')
        capture_status = {'selection':'Đang nhận chữ bôi đen…', 'region':'Kéo chọn vùng chữ trên màn hình…', 'image':'Đang đọc chữ trong ảnh…',
            'clipboard':'Đang đọc Clipboard và dịch…', 'file':'Đang đọc file và dịch…'}.get(args.get('mode'),'Đang nhận chữ…')
        if operation != "check_mini_readiness":
            self.update(busy=True, phase='working', expanded=(self.presentation.extent == 'expanded'), hasWorkbench=True, agentSummary='', agentIncomplete=False,
                lastOperation=operation, error=False, translationSettingsSuggested=False,
                finderSettingsSuggested=False, imageInputSuggested=False,
                status={'plan_folder_organization':'Đang chuẩn bị bản xem trước…',
                    'apply_folder_organization':'Đang sắp xếp file…', 'undo_folder_organization':'Đang hoàn tác…',
                    'get_last_organization':'Đang đọc nhật ký…', 'find_files':'Đang tìm trong thư mục đã chọn…',
                    'translate_text':'Đang dịch…', 'capture_translate':capture_status,
                    'correct_translate':'Đang ghi nhận chữ đã sửa và dịch lại…',
                    'open_file':'Đang mở file…', 'reveal_file':'Đang hiện trong Finder…'}.get(operation,'Đang thực hiện…'))
        if operation == "check_mini_readiness":
            self.update(busy=True)
        # Readiness uses the same registered tool/service in an isolated runtime.
        # It must not dismiss a pending clarification in the user's task session.
        session = MiniSession(self.settings, artifact_store=self.session.runtime.artifact_store) if operation == 'check_mini_readiness' or preserve_region else self.session
        job = MiniJob(session, operation, args, query, generation, input_context)
        self.job = job
        def deliver_result(value):
            if job.generation == self.generation:
                self.render(value)
            elif value.get('invocation_id'):
                self.quicklook_journal.record('discarded_result', invocation_id=value['invocation_id'], generation=job.generation)
        job.result.connect(deliver_result)
        job.progress.connect(lambda message: self.update(status=message) if job.generation == self.generation and operation != 'check_mini_readiness' else None)
        job.captured.connect(lambda source: self.remember_capture_position(job, source))
        job.quicklookStage.connect(lambda event: self.quicklook_journal.record(**event))
        job.finished.connect(lambda: self.finished(job))
        job.start()

    def remember_capture_position(self, job, source):
        if job.generation == self.generation:
            artifact = source['artifact']
            if job.args.get('mode') == 'selection':
                self.quicklook_journal.record('capture_succeeded', invocation_id=job.input_context.get('quicklook_invocation_id'),
                    artifact_id=artifact.id, generation=job.generation)
            if job.args.get('preserve_until_capture'):
                self.remember_task()
                if job.args.get('mode') == 'selection':
                    self._selection_return = None
                self.presentation.begin_task()
                self._result_ref = None
                self.session.clear_pending()
                # The isolated session now owns the selected task, including
                # any clarification needed by the following translation.
                self.session = job.session
                self.clear_ocr_source()
                self.clearImagePreview()
                self.finder_artifact = self.organization_artifact = None
                self.update(pinned=False, canApplyOrganization=False, canUndoOrganization=False, view='notice',
                    finderHits=[], text='', meta='', translationDetails='', translationNotice='',
                    sameLanguageNotice='', agentSummary='', agentIncomplete=False,
                    requestText='Chữ bôi đen' if job.args.get('mode') == 'selection' else 'Vùng chữ đã chọn')
                self._region_previous = None
                region_image = source.get('region_image')
                if region_image:
                    self._last_image = region_image
                    self.update(imagePreviewUrl=self.image_preview.set_input(region_image), imageLabel='Vùng chữ đã chọn')
            if artifact.payload.get('source_kind') in ('image','region') or job.args.get('look_input'):
                self._ocr_source_ref = {'artifact_id':artifact.id, 'revision':artifact.revision}
                self._ocr_current_text = artifact.payload['text']
                self._translation_args = dict(source['translation_args'])
                self.update(ocrText=self._ocr_current_text, ocrCommittedText=self._ocr_current_text,
                    captureSourceKind=artifact.payload['source_kind'],
                    captureSourceApp=job.input_context.get('selection_app','') if artifact.payload['source_kind']=='selection' else '',
                    lookSource=bool(job.args.get('look_input')) or self._state['lookSource'],
                    hasOcrSource=True, canRetryTranslation=True,
                    ocrOriginalText=self._state['ocrOriginalText'] if job.operation == 'correct_translate' else artifact.payload.get('ocr_raw_text', self._ocr_current_text),
                    ocrPreparationNotice=('Đã nối các dòng chữ cùng đoạn để dịch. Chữ nhận ban đầu vẫn được giữ.'
                        if (artifact.payload.get('ocr_normalization') or {}).get('joined_line_indexes') else ''))
            if job.args.get('mode') == 'region':
                self._capture_position = QCursor.pos()
            self.update(status='Đang dịch…')
            if job.args.get('mode') == 'selection' and self._selection_present_generation == job.generation:
                self._selection_present_generation = None
                self.selectionAnchorRequested.emit(source.get('selection_geometry') or {})
                self._presentation_invocation_id = job.input_context.get('quicklook_invocation_id')
                self.quicklook_journal.record('present_requested', invocation_id=self._presentation_invocation_id)
                self.lookRequested.emit()

    def finished(self, job):
        self.job = None
        if job.stop.is_set():
            job.session.clear_pending()
        job.deleteLater()
        if self.quitting:
            QGuiApplication.quit()
        elif self.pending:
            self.start_pending()
        else:
            self.update(busy=self._state['receivingImage'])

    def render(self, value):
        if value.get('recording_error'):
            self.update(settingsNotice='Kết quả đã có, nhưng chưa ghi được hồ sơ kiểm tra.')
        response = value.get('response')
        error = value.get('error') or (response.error if response else None)
        if value.get('capture_mode') == 'selection' and response is None and not error:
            error = 'selection_response_missing'
        invocation = value.get('invocation_id')
        if invocation:
            stage = ('capture_failed' if error and self._region_previous is not None else 'translation_failed' if error
                     else 'needs_input' if response and response.pending_input_request else 'execution_completed')
            safe_codes = ('selection_accessibility_required', 'selection_source_changed', 'selection_unavailable',
                'selection_empty', 'selection_source_unresponsive', 'snippet_too_long', 'cancelled', 'capture_artifact_missing', 'selection_response_missing')
            reason = next((code for code in safe_codes if code in str(error)), 'other_failure' if error else None)
            self.quicklook_journal.record(stage, invocation_id=invocation, reason=reason,
                execution_id=response.execution_id if response else None)
        if value.get('operation') == 'check_mini_readiness':
            checks = next((a.payload for a in (response.artifacts if response else []) if a.kind == 'mini_readiness'), None)
            self.update(readinessSummary=self.readiness_summary(checks['checks']) if checks else self._state['readinessSummary'],
                readinessBusy=False,
                readiness=checks['checks'] if checks else self._state['readiness'],
                readinessStatus=('Đã kiểm tra thành phần. Dùng thử để xác nhận trên máy này.' if checks and checks['status']=='ready' else
                    'Một số chức năng cần xử lý. Bạn vẫn có thể dùng phần đã sẵn sàng.' if checks else 'Chưa kiểm tra được. Hãy thử lại.'))
            return
        model_loop = bool(response and (response.qa_telemetry or {}).get('mini_execution_path') == 'model_loop')
        if model_loop:
            # Preserve the public conclusion beside real artifacts; the newest
            # artifact alone cannot stand in for a whole compound request.
            self.update(agentSummary=response.answer or '',
                agentIncomplete=response.completion_status != 'completed')
        region = value.get('capture_mode') == 'region'
        selection = value.get('capture_mode') == 'selection'
        if (region or selection) and self._region_previous is not None and (error or response is None):
            self.restore_region_previous()
            if error and not str(error).startswith('cancelled'):
                if selection:
                    self.presentation.read()
                    self.update(selectionNotice=self.friendly_error(str(error)),
                        selectionNeedsPermission='selection_accessibility_required' in str(error))
                    if self._selection_present_generation == self.generation:
                        self._selection_present_generation = None
                        self._presentation_invocation_id = invocation
                        self.quicklook_journal.record('present_requested', invocation_id=invocation)
                        self.lookRequested.emit()
                else:
                    self.update(phase='error', error=True, status=self.friendly_error(str(error)))
            elif selection:
                self.restore_selection_view()
            return
        if error:
            self.update(readinessBusy=False)
            if any(code in str(error) for code in ('source_expired','source_integrity_mismatch','stale_source_ref')):
                self.presentation.workspace = 'result'
                if self.presentation.surface in ('ocr', 'source'):
                    self.presentation.open('result')
                self.update(canRetryTranslation=False, hasOcrSource=False, canRetryRequest=False)
            cancelled = str(error).startswith('cancelled')
            self.update(phase='cancelled' if cancelled else 'error', error=not cancelled,
                translationSettingsSuggested=any(code in str(error) for code in (
                    'translation_rate_limited', 'translation_quota_exhausted',
                    'translation_api_key_missing', 'translation_auth_failed', 'translation_local_unavailable', 'online_translation_not_enabled', 'api_key_missing')),
                finderSettingsSuggested=any(code in str(error) for code in ('no_search_roots', 'scope_revoked', 'spotlight_permission_denied', 'organization_folder_outside_scope', 'organization_scope_changed')),
                imageInputSuggested=any(code in str(error) for code in ('ocr_empty', 'image_input_invalid', 'source_expired', 'stale_source_ref', 'source_integrity_mismatch')),
                status='Đã dừng tác vụ.' if cancelled else self.friendly_error(str(error)))
            return
        if response is None:
            self.update(phase='error', view='notice', error=True, status='Tác vụ không trả về kết quả.')
            return
        if response.pending_input_request:
            self.complete_surface()
            self.presentation.composer_visible = True
            self.update(phase='needs_input', view='notice', text='', meta='', finderHits=[],
                finderSettingsSuggested=response.pending_input_request.operation_name == 'find_files',
                imageInputSuggested=False,
                status=response.pending_input_request.prompt)
            return
        for artifact in reversed(response.artifacts):
            data = artifact.payload

            if artifact.kind in ('organization_plan', 'organization_receipt'):
                self.clear_ocr_source()
                self.organization_artifact = artifact
                is_plan = artifact.kind == 'organization_plan'
                plan = data if is_plan else data.get('plan', {})
                rows = [dict(name=x['name'], destination=x['group']+'/'+x['name'], state='preview') for x in plan.get('moves', [])] if is_plan else [dict(name=x['name'], destination=x['group']+'/'+x['name'], state=x['state'], reason=x.get('reason','')) for x in data.get('entries', [])]
                moved = sum(x['state']=='moved' for x in rows)
                conflicts = sum(x['state'] in ('undo_conflict','identity_conflict') for x in rows)
                skipped_moves = sum(x['state'] in ('skipped', 'restored_conflict') for x in rows)
                counts = sum(plan.get('skipped', {}).values())
                title = f"Xem trước: {len(rows)} file · bỏ qua {counts}" if is_plan else f"Đã chuyển {moved} file · bỏ qua {skipped_moves} · {conflicts} xung đột"
                if data['status'] == 'undone': title = 'Đã hoàn tác; các thư mục trống được giữ lại.'
                if data['status'] == 'empty': title = 'Chưa có lần sắp xếp nào.'
                grouped = {}
                for row in rows:
                    group = row['destination'].split('/', 1)[0]
                    grouped.setdefault(group, []).append(row)
                groups = [dict(name=name, count=len(items), rows=items) for name, items in grouped.items()]
                self.complete_surface()
                self.update(view='organization', organization=data, organizationRows=rows, organizationGroups=groups, organizationRecoverySuggested=False,
                    canApplyOrganization=is_plan and bool(rows),
                    canUndoOrganization=not is_plan and any(x['state'] in ('moved','move_pending','undo_pending','undo_conflict') for x in rows),
                    phase='partial' if model_loop and self._state['agentIncomplete'] else 'result', status=title, text='', meta=plan.get('root',''), finderHits=[])
                return
            if artifact.kind == 'finder_results':
                self.remember_finder_diagnostic(data)
                self.clear_ocr_source()
                self.finder_artifact = artifact
                hits = [dict(hit, kind='file', is_pdf=Path(hit['path']).suffix.lower()=='.pdf',
                    display_path=hit['path'], match_reason='Spotlight') for hit in data['hits']]
                partial = data.get('status') == 'partial' or bool(data.get('provider_errors'))
                status = (f"Tìm thấy {len(hits)} file" if hits else 'Chưa tìm thấy file trong thư mục đã chọn.')
                if partial:
                    done = data.get('coverage', {}).get('completed_roots')
                    total = data.get('coverage', {}).get('roots')
                    if not hits:
                        status = 'Spotlight chưa tìm xong. Chưa thể kết luận có file hay không.'
                    else:
                        status += (f' · Đã tìm xong {done}/{total} thư mục.'
                                   if done is not None and total else ' · Một số thư mục chưa tìm xong.')
                if any(e.get('code') == 'spotlight_permission_denied' for e in data.get('provider_errors', [])):
                    status += ' macOS chưa cho RAT đọc một số thư mục đã chọn.'
                self.complete_surface()
                self.update(phase='partial' if partial or (model_loop and self._state['agentIncomplete']) else 'result', view='finder', finderHits=hits,
                    finderSettingsSuggested=partial or not hits,
                    text='', meta='Chọn một file để mở hoặc hiện trong Finder', status=status)
                return

            if artifact.kind == 'translation':
                self._result_ref = {'artifact_id':artifact.id, 'revision':artifact.revision}
                source_capture = data.get('source_capture') or {}
                if not source_capture:
                    self.clear_ocr_source()
                elif self._ocr_source_ref == source_capture.get('source_ref'):
                    self._translation_args = {'source_ref':dict(self._ocr_source_ref),
                        'source_language':data['source_language'], 'target_language':data['target_language'],
                        'style':data.get('style','faithful')}
                languages = {'vi':'Tiếng Việt', 'en':'Tiếng Anh', 'ja':'Tiếng Nhật', 'ko':'Tiếng Hàn',
                    'zh':'Tiếng Trung', 'fr':'Tiếng Pháp', 'de':'Tiếng Đức', 'es':'Tiếng Tây Ban Nha',
                    'auto':'Tự nhận diện'}
                meta=f"{languages.get(data['source_language'], data['source_language'])} → {languages.get(data['target_language'], data['target_language'])}"
                if data.get('local_model'):
                    meta = 'Dịch trên máy · ' + meta
                provenance = (data.get('source_capture') or {}).get('input_provenance') or {}
                origin = {'selected_file':'Ảnh đã chọn', 'dropped_file':'Ảnh kéo thả', 'dropped_image':'Ảnh kéo thả', 'clipboard_file':'File ảnh đã dán',
                    'clipboard_image':'Ảnh đã dán'}.get(provenance.get('origin'))
                if origin:
                    meta = origin + ' · ' + meta
                if (data.get('source_capture') or {}).get('text_origin') == 'user_edit':
                    meta = 'Chữ đã sửa · ' + meta
                provider_name = 'OPUS-MT / Argos · trên máy' if data['provider'] == 'offline_argos' else data['provider']
                details = f"Dịch vụ: {provider_name}\n" + '\n'.join(data.get('warnings', []))
                notice = '\n'.join(w for w in data.get('warnings', []) if not w.startswith('Đã dùng MyMemory'))
                if data['provider'] == 'same_language':
                    meta += ' · Nội dung đã ở ngôn ngữ đích'
                if provenance.get('kind') == 'file' and provenance.get('file_name'):
                    meta = f"{provenance['file_name']} · {meta}"
                can_return = bool(self.finder_artifact and provenance.get('kind') == 'file')
                partial = data['status'] == 'partial'
                self.complete_surface()
                self.update(phase='partial' if partial or (model_loop and self._state['agentIncomplete']) else 'result', view='translation', finderHits=[],
                    text=data['text'], meta=meta, translationDetails=details.strip(), translationNotice=notice,
                    sameLanguageNotice=('Đoạn này đã là ' + languages.get(data['target_language'], data['target_language']) + '.' if data['provider'] == 'same_language' else ''),
                    status='Chưa dịch hết văn bản' if partial else 'Bản dịch',
                    canReturnToFinder=can_return)
                return
        if value.get('operation') in ('open_file', 'reveal_file'):
            self.update(phase='result', status='Đã mở file.' if value['operation'] == 'open_file' else 'Đã hiện trong Finder.')
            self.interactionCompleted.emit()
        else:
            self.complete_surface()
            incomplete = model_loop and self._state['agentIncomplete']
            self.update(phase='partial' if incomplete else 'result', view='notice', text=response.answer or '',
                status='Chưa hoàn tất toàn bộ yêu cầu.' if incomplete else 'Đã hoàn tất.')

    def remember_finder_diagnostic(self, data):
        """One replaceable receipt; no filenames, paths, predicates or text."""
        diagnostic = {'version': 'M5.16-source', 'status': data.get('status'),
            'coverage': data.get('coverage'), 'hit_count': data.get('hit_count'),
            'provider_errors': data.get('provider_errors'), 'diagnostics': data.get('diagnostics')}
        try:
            folder = state_directory()
            folder.mkdir(parents=True, exist_ok=True)
            pending = folder/'.last-finder.json'
            pending.write_text(json.dumps(diagnostic, ensure_ascii=False), encoding='utf-8')
            pending.replace(folder/'last-finder.json')
        except OSError:
            logging.getLogger(__name__).debug('finder_receipt_unavailable')

    @staticmethod
    def readiness_summary(checks):
        by_key = {item['key']: item for item in checks}
        groups = [('translation', 'Dịch Anh ↔ Việt', ('ctranslate2','sentencepiece','en-vi','vi-en','models')),
                  ('image', 'Dịch ảnh', ('Vision',)), ('finder', 'Tìm file', ('spotlight','folders'))]
        summaries = []
        for key, label, members in groups:
            items = [by_key[name] for name in members if name in by_key]
            state = 'action_required' if any(x['state']=='action_required' for x in items) else 'unverified' if not items or any(x['state']=='unverified' for x in items) else 'ready'
            summaries.append(dict(key=key, label=label, state=state,
                detail=' · '.join(x['detail'] for x in items if x['state']=='action_required') or
                    ('Có thành phần; chưa xác nhận toàn bộ luồng.' if state=='ready' else 'Bạn có thể dùng thử; quyền thư mục và gói dịch được kiểm tra khi cần.')))
        return summaries

    @staticmethod
    def friendly_error(error):
        messages = {
            'online_translation_not_enabled':'MyMemory chưa được bật. Mở Cài đặt để chọn dịch trên máy hoặc cho phép MyMemory; đoạn chữ vẫn được giữ.',
            'organization_folder_outside_scope':'Thư mục này chưa thuộc phạm vi RAT. Thêm thư mục trong Cài đặt, rồi xem trước lại.',
            'organization_stale_preview':'Bản xem trước đã quá 30 phút hoặc đã đổi. Hãy tạo bản xem trước mới.',
            'organization_scope_changed':'Danh sách thư mục đã đổi. Hãy tạo bản xem trước mới.',
            'organization_folder_changed':'Thư mục đã bị thay thế. Hãy chọn và xem trước lại.',
            'organization_explicit_approval_required':'Chỉ áp dụng bằng nút trên bản xem trước hiện tại.',
            'spotlight_permission_denied':'macOS chưa cho RAT đọc thư mục đã chọn. Kiểm tra quyền của RAT hoặc chọn thư mục khác.',
            'no_search_roots':'Chọn ít nhất một thư mục trong Cài đặt để bắt đầu tìm file.',
            'scope_revoked':'Danh sách thư mục đã thay đổi. Hãy tìm lại trước khi mở file.',
            'translation_local_unavailable':'Gói dịch trên máy chưa sẵn sàng. Hãy mở lại app hoặc dùng lại bản ZIP đầy đủ; chữ vẫn được giữ.',
            'translation_quota_exhausted':'Dịch vụ đã hết hạn mức. Chữ vẫn được giữ; đổi dịch vụ hoặc chờ hạn mức khôi phục.',
            'translation_rate_limited':'Dịch vụ đang giới hạn lượt dịch. Chữ vẫn được giữ; hãy thử lại sau ít phút.',
            'translation_auth_failed':'Dịch vụ chưa chấp nhận cấu hình truy cập. Kiểm tra cài đặt dịch; chữ vẫn được giữ.',
            'translation_api_key_missing':'Dịch vụ này chưa được cấu hình. Chọn dịch vụ khác trong Cài đặt; chữ vẫn được giữ.',
            'translation_timeout':'Dịch vụ phản hồi quá lâu. Chữ vẫn được giữ; bạn có thể thử dịch lại.',
            'translation_tls_failed':'Chưa kết nối an toàn được với dịch vụ dịch. Kiểm tra ngày giờ máy và mạng; chữ vẫn được giữ.',
            'translation_network_error':'Chưa kết nối được dịch vụ dịch. Kiểm tra mạng rồi thử lại; chữ vẫn được giữ.',
            'translation_provider_error':'Dịch vụ dịch chưa trả được kết quả. Chữ vẫn được giữ; hãy thử lại sau.',
            'mini_llm_disabled':'Chức năng này cần bật suy luận cloud trong Cài đặt. Nguồn chữ vẫn được giữ.',
            'translation_failed':'Chưa dịch được lúc này. Chữ vẫn được giữ; kiểm tra mạng rồi thử lại.'}
        for code, message in messages.items():
            if code in error:
                return message
        if any(code in error for code in ('stale_result_ref', 'result_expired', 'invalid_result_ref')):
            return 'Kết quả trước không còn hợp lệ. Hãy mở lại nguồn và thực hiện lại yêu cầu.'
        if any(code in error for code in ('source_integrity_mismatch', 'source_expired', 'stale_source_ref')):
            return 'Nguồn chữ cũ không còn hợp lệ. Hãy thả lại ảnh hoặc dán lại nội dung để dịch.'
        if 'selection_accessibility_required' in error:
            return 'Cho phép RAT trong Cài đặt hệ thống → Quyền riêng tư & Bảo mật → Trợ năng. Sau đó bôi đen chữ và bấm phím tắt Quick Look lại.'
        if 'selection_empty' in error:
            return 'Chưa thấy chữ được chọn. Bôi đen một đoạn rồi bấm lại.'
        if 'selection_source_unresponsive' in error:
            return 'App nguồn chưa phản hồi. Chờ một chút rồi thử lại, hoặc copy và chọn Dán chữ.'
        if 'selection_source_changed' in error:
            return 'App nguồn đã đổi. Bôi đen chữ trong app cần đọc rồi bấm phím tắt Quick Look lại.'
        if 'selection_unavailable' in error:
            return 'Chưa lấy được chữ bôi đen từ app này. Bạn có thể dán chữ hoặc chọn vùng ảnh trong menu.'
        if 'selection_response_missing' in error:
            return 'Quick Look chưa trả về kết quả. Mã QL_NO_RESPONSE. Công việc trước vẫn được giữ.'
        if 'screen_capture_denied' in error:
            return 'Cho phép Ghi màn hình trong macOS để chọn vùng chữ.'
        if 'ocr_empty' in error:
            return 'Chưa đọc được chữ trong ảnh. Hãy chụp vùng rõ hơn hoặc gõ nội dung cần dịch vào ô nhập.'
        if 'image_input_invalid' in error:
            return 'Chưa đọc được ảnh. Hãy thả một ảnh PNG/JPG đã lưu, hoặc chụp vùng chữ nhỏ hơn.'
        if 'api_key_missing' in error:
            return 'Yêu cầu này cần Agent cloud chưa được cấu hình. Bạn có thể hỏi từng bước: tìm file, hoặc gửi đoạn cần dịch.'
        if 'clipboard' in error.lower() or 'empty_text' in error.lower():
            return 'Clipboard chưa có văn bản. Copy một đoạn chữ rồi thử lại.'
        if 'stale_resource' in error or 'resource_not_found' in error or 'FileNotFound' in error:
            return 'File đã thay đổi hoặc không còn ở đó. Hãy tìm lại trước khi mở.'
        if 'permission' in error.lower():
            return 'RAT chưa đọc được thư mục này. Kiểm tra quyền truy cập trong macOS.'
        return 'Chưa thực hiện được lúc này. Nội dung vẫn được giữ; bạn có thể thử lại.'

    @pyqtSlot(int)
    def openSelectedHit(self, index):
        self.file_action(index, 'open_file')

    @pyqtSlot(int)
    def revealSelectedInFinder(self, index):
        self.file_action(index, 'reveal_file')

    @pyqtSlot(int)
    def translateSelectedHit(self, index):
        artifact = self.finder_artifact
        if self._state['busy'] or not artifact or not 0 <= index < len(artifact.payload['hits']):
            return
        hit = artifact.payload['hits'][index]
        self.update(requestText="Dịch file: " + hit['title'])
        self.enqueue('capture_translate', dict(mode='file', file_path=hit['path'],
            artifact_id=artifact.id, revision=artifact.revision, resource_id=hit['resource_id'],
            look_input=True, source_language=self.settings['source_language'],
            target_language=self.settings['target_language']))

    @pyqtSlot()
    def returnToFinderResults(self):
        if self._state['busy'] or not self.finder_artifact:
            return
        raw_hits = self.finder_artifact.payload.get('hits', [])
        hits = [dict(hit, kind='file', is_pdf=Path(hit['path']).suffix.lower() == '.pdf',
            display_path=hit['path'], match_reason='Spotlight') for hit in raw_hits]
        self.update(phase='result', view='finder', finderHits=hits, text='',
            status=f"Đã tìm thấy {len(hits)} mục",
            meta='Chọn một file để mở hoặc hiện trong Finder',
            canReturnToFinder=False)

    def file_action(self, index, operation):
        artifact = self.finder_artifact
        if self._state['busy'] or not artifact or not 0 <= index < len(artifact.payload['hits']):
            return
        hit = artifact.payload['hits'][index]
        self.enqueue(operation, dict(artifact_id=artifact.id, revision=artifact.revision,
            resource_id=hit['resource_id']))

    @pyqtSlot()
    def copyResult(self):
        text = self._state['text'] or '\n'.join(h['path'] for h in self._state['finderHits'])
        if text:
            QGuiApplication.clipboard().setText(text)
            if self._state.get('view') == 'translation':
                self.update(status='Đã sao chép bản dịch')
            else:
                self.interactionCompleted.emit()

    @pyqtSlot(str)
    def copyLook(self, displayed_text):
        if displayed_text:
            QGuiApplication.clipboard().setText(displayed_text)
            self.interactionCompleted.emit()

    @pyqtSlot()
    def cancel(self):
        if self._selection_invocation_id:
            self.quicklook_journal.record('cancel_requested', invocation_id=self._selection_invocation_id)
        self.generation += 1
        self._receiving_token = None
        self.pending = None
        if self._region_previous is not None:
            if self.job:
                self.job.stop.set()
            self.restore_region_previous()
            self.restore_selection_view()
            self._selection_present_generation = None
            self._presentation_invocation_id = None
            self.update(receivingImage=False, dropActive=False, busy=self.job is not None)
            return
        if self.job:
            self.job.stop.set()
            if self.job.operation == 'check_mini_readiness':
                self.update(readinessBusy=False, readinessStatus='Đã dừng kiểm tra.', busy=True)
                return
        else:
            self.session.clear_pending()
        self.update(phase='cancelled', status='Đã yêu cầu dừng.', error=False,
            receivingImage=False, dropActive=False, busy=self.job is not None)

    @pyqtSlot('QVariantMap', result=str)
    @pyqtSlot('QVariantMap', str, result=str)
    def savePreferences(self, changes, secret=''):
        if self.job:
            return 'Đợi tác vụ kết thúc trước khi đổi cài đặt.'
        try:
            updated = dict(self.settings)
            roots = changes.get('roots', updated['roots'])
            roots = [str(Path(p).expanduser().resolve()) for p in roots if str(p).strip()]
            if any(not Path(p).is_dir() for p in roots):
                return 'Chọn thư mục đang tồn tại, hoặc bỏ thư mục không còn dùng.'
            updated.update(roots=roots)
            for name in ('source_language', 'target_language', 'translation_provider', 'free_fallback', 'provider', 'model', 'llm_enabled'):
                if name in changes:
                    updated[name] = changes[name]
            if type(updated.get('llm_enabled', False)) is not bool:
                return 'Kiểm tra tùy chọn suy luận cloud.'
            updated.setdefault('llm_enabled', False)
            if not updated['llm_enabled'] and updated['translation_provider'] == 'llm':
                updated['translation_provider'] = 'automatic'
            if updated['provider'] not in ('openai', 'deepseek', 'groq') or updated['translation_provider'] not in ('automatic', 'google_gtx', 'mymemory', 'llm', 'deepl', 'google'):
                return 'Chọn một dịch vụ được hỗ trợ.'
            for name, maximum in (('source_language',35), ('target_language',35), ('model',128)):
                if not isinstance(updated[name],str) or not updated[name].strip() or len(updated[name]) > maximum or '\0' in updated[name]:
                    return 'Kiểm tra ngôn ngữ và tên model trong cài đặt.'
                updated[name] = updated[name].strip()
            if updated['target_language'] == 'auto' or type(updated['free_fallback']) is not bool:
                return 'Chọn ngôn ngữ đích và tùy chọn dự phòng hợp lệ.'
            # Preserve observed text/correction artifacts when switching provider.
            # Keep visible results; file actions still validate the new scopes.
            session = MiniSession(updated, artifact_store=self.session.runtime.artifact_store)
            session.pending_route = self.session.pending_route
            session.previous_goal = self.session.previous_goal
            session.runtime.dispatcher.state.pending_input_request = self.session.runtime.dispatcher.state.pending_input_request
            if secret.strip():
                provider = (updated['translation_provider'] if updated['translation_provider'] in ('deepl', 'google')
                            else updated['provider'] if updated['llm_enabled'] else updated['translation_provider'])
                if provider not in ('openai', 'deepseek', 'groq', 'deepl', 'google'):
                    return 'Dịch vụ miễn phí không dùng API key. Hãy bỏ key hoặc chọn dịch vụ có key.'
                # Never put credentials into settings, snapshots, artifacts or logs.
                keychain_key(provider, secret)
            save_settings(updated)
            if self._translation_args:
                for key in ('source_language','target_language'):
                    if updated[key] != self.settings[key]:
                        self._translation_args[key] = updated[key]
            if self._retry_request:
                operation, arguments, query = self._retry_request
                arguments = dict(arguments)
                if operation in ('capture_translate', 'translate_text'):
                    for key in ('source_language', 'target_language'):
                        arguments[key] = updated[key]
                self._retry_request = operation, arguments, query
            scopes_changed = updated['roots'] != self.settings['roots']
            self.settings, self.session = updated, session
            if scopes_changed:
                self.organization_artifact = None
                self.update(canApplyOrganization=False, canUndoOrganization=False,
                    organizationRecoverySuggested=self._state['view'] == 'organization')
            if self._state['translationSettingsSuggested'] and self._state['phase'] == 'error':
                self._state['status'] = 'Đã cập nhật cài đặt. Bấm Thử lại để dịch đoạn chữ đã giữ.'
            self.update(translationSettingsSuggested=False, settingsNotice='Đã lưu cài đặt.' + (' Hãy xem trước lại nếu đã đổi thư mục.' if scopes_changed else ''))
            return ''
        except Exception as exc:
            return 'Chưa lưu được: ' + str(exc)

    @pyqtSlot()
    def quit(self):
        self.quitting = True
        self.cancel()
        self.hideRequested.emit()
        if not self.job:
            QGuiApplication.quit()
