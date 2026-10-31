"""Qt Quick projection of MiniSession; business execution stays in its tools."""
from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from rat.os.hotkey_chords import CHORDS, DEFAULT_CHORD, chord
import json
import logging
import os
import sys
import time
import subprocess
from PyQt6.QtCore import QObject, QPoint, QTimer, QUrl, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QCursor

from rat.engine.mini_settings import read_settings, save_settings, keychain_key, state_directory
from rat.mini import MiniSession
from rat.ui.mini_diagnostics import BUILD, write_diagnostic
from rat.ui.quick_look_journal import QuickLookJournal
from rat.ui.mini_presentation import MiniPresentation
from rat.ui.image_input import IMAGE_SUFFIXES, ENCODED_IMAGE_TYPES, image_from_mime, image_from_url
from rat.ui.image_preview import ImagePreviewProvider
from rat.os.permissions import runtime_identity
from rat.ui.mini_job_worker import (
    MiniJob, format_compact_display_path, format_translation_artifact_view,
    default_controller_state, REGION_PREVIOUS_FIELDS, render_journal_stage, render_error_suggestions,
    is_new_task_operation, get_frontmost_app_info, pending_task_initial_updates, capture_position_ocr_updates,
    process_render_artifacts,
    format_user_error_message, format_organization_artifact_view, format_readiness_summary,
    record_finder_diagnostic, format_diagnostic_events, export_diagnostics_to_file,
    initial_operation_status, validate_and_apply_preferences, parse_pasted_mime_content,
    pack_task_history_item, HISTORY_FIELDS,
    format_finder_return_hits, handle_file_action, change_shortcut_setting,
    write_ui_state_diagnostic, build_controller_snapshot, save_preferences_settings, parse_image_url_input,
)

__all__ = [
    "MiniQuickController", "MiniJob", "format_compact_display_path",
    "format_translation_artifact_view", "format_user_error_message",
]

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
        show_welcome = not self.settings.get("setup_completed") or self.settings.get("permission_hello_version", 0) < 1
        if sys.platform == "darwin" and not os.environ.get("PYTEST_CURRENT_TEST"):
            from rat.os.permissions import is_accessibility_trusted
            if not is_accessibility_trusted():
                show_welcome = True
        self.presentation = MiniPresentation(surface="welcome" if show_welcome else "result")
        self._hold_chat_requested = False
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
        self._state = default_controller_state(self.settings)
        self.shortcut_ack_timer = QTimer(self)
        self.shortcut_ack_timer.setSingleShot(True)
        self.shortcut_ack_timer.timeout.connect(lambda: self.update(shortcutAck=''))
        self.record_ui_state()
        if self.presentation.surface == 'welcome' or not os.environ.get('PYTEST_CURRENT_TEST'):
            QTimer.singleShot(0, lambda: self.checkReadiness(False))

    @pyqtProperty('QVariantMap', notify=changed)
    def snapshot(self):
        return build_controller_snapshot(self._state, self.presentation.snapshot(), self.settings,
                                         self._task_history, self.diagnostic_events())

    @pyqtProperty('QVariantMap', notify=changed)
    def preferences(self):
        return dict(self.settings)

    def record_ui_state(self):
        write_ui_state_diagnostic(self.presentation, self._state, self.generation)

    def update(self, **values):
        self._state.update(values)
        self.record_ui_state()
        self.changed.emit()

    @pyqtSlot()
    def summonLook(self):
        if not self._state['setupCompleted']:
            self.presentation.open('welcome'); self.update(); self.presentRequested.emit(); return
        if self._state['selectionNotice']:
            self.recallLookResult(); return
        self._state['selectionNotice'] = ''
        self.presentation.open('result'); self.presentation.read(); self.update(); self.lookRequested.emit()

    @pyqtSlot()
    def dismissLookResult(self):
        if self._selection_invocation_id:
            self.quicklook_journal.record('dismissed', invocation_id=self._selection_invocation_id)
        self._selection_present_generation = self._presentation_invocation_id = None
        self.update(); self.lookResultDismissed.emit()

    @pyqtSlot()
    def recallLookResult(self):
        if self._state['selectionNotice']:
            self.returnToTask(); self.lookRequested.emit(); return
        self._state['selectionNotice'] = ''
        self.presentation.open('result')
        self.presentation.read() if self._state['hasWorkbench'] else self.presentation.compose()
        self.update(); self.lookRequested.emit()

    @pyqtSlot()
    def returnToTask(self):
        if self._state['selectionNotice']:
            if self._selection_return is not None: self.restore_selection_view()
            elif self._state['hasWorkbench']: self.presentation.read()
            else: self.presentation.compose()
            self.update(selectionNotice='', selectionNeedsPermission=False); return
        self.update()

    @pyqtSlot()
    def summonMinimal(self):
        if not self._state['setupCompleted']:
            self.presentation.open('welcome'); self.update(); self.presentRequested.emit(); return
        if self._state['selectionNotice']: self.returnToTask()
        self._state['selectionNotice'] = ''
        self.presentation.open('result'); self.presentation.compose(); self.update(); self.minimalRequested.emit()

    @pyqtSlot()
    def focusLook(self):
        self.update(); self.lookFocusRequested.emit()

    def _effective_source_language(self):
        src = self.settings.get('source_language', 'auto')
        tgt = self.settings.get('target_language', 'vi')
        return 'auto' if src == tgt else src

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
            source_language=self._effective_source_language(), target_language=self.settings['target_language']))

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
                source_language=self._effective_source_language(),
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
        if not self._state['busy']: self.presentation.selections[self.presentation.task_id] = max(0, start), max(0, end)

    @pyqtSlot(str, int, float)
    def rememberReadingAnchor(self, text, position, delta):
        if not self._state['busy']:
            length = len(text.encode('utf-16-le')) // 2
            self.presentation.reading_anchor = (text, max(0, min(position, length)), float(delta))

    @pyqtSlot()
    def toggleSource(self):
        self.presentation.source_visible = not self.presentation.source_visible
        self.presentation.resize(True); self.update(expanded=True)

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
        if self._hold_chat_requested:
            self.presentation.composer_visible = True
            self._hold_chat_requested = False

    @pyqtSlot()
    def escalateToVCoTChat(self):
        self._hold_chat_requested = True
        self.presentation.open('result')
        self.presentation.compose()
        self.update(bubbleCollapsed=False)
        self.minimalRequested.emit()

    @pyqtSlot()
    def flipTargetLanguageAndRetranslate(self):
        new_target = 'en' if self.settings.get('target_language') == 'vi' else 'vi'
        self.settings['target_language'] = new_target
        save_settings(self.settings)
        self.update(targetLanguage=new_target)
        if hasattr(self, '_ocr_source_ref') and self._ocr_source_ref and hasattr(self, '_translation_args') and self._translation_args:
            self._translation_args['target_language'] = new_target
            self._translation_args['source_language'] = 'auto'
            self.enqueue('translate_text', dict(self._translation_args))
        elif self._state.get('requestText') or self._state.get('text') or self._state.get('ocrText'):
            src_text = self._state.get('ocrText') or self._state.get('text') or self._state.get('requestText')
            self.enqueue('translate_text', {'text': src_text, 'source_language': 'auto', 'target_language': new_target})

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
            save_settings(updated); self.settings = updated
            self.presentation.back(); self.presentation.compose(); self.update(setupCompleted=True)
            return ''
        except OSError:
            return 'Chưa lưu được thiết lập. Bạn vẫn có thể đóng cửa sổ để dùng RAT.'

    @pyqtSlot(QUrl)
    def organizeFolder(self, url):
        path = self.localFolderPath(url)
        if not path: return
        self.clearImagePreview(); self.update(requestText='Sắp xếp ' + path)
        self.enqueue('plan_folder_organization', {'folder':path, 'rule':'type'})

    @pyqtSlot()
    def applyOrganization(self): self._approved_organization('apply_folder_organization', 'organization_plan')

    @pyqtSlot()
    def undoOrganization(self): self._approved_organization('undo_folder_organization', 'organization_receipt')

    def _approved_organization(self, operation, kind):
        artifact = self.organization_artifact
        if self.job or self._state['view'] != 'organization' or not artifact or artifact.kind != kind: return
        pin = {'artifact_id':artifact.id, 'revision':artifact.revision}
        self.update(canApplyOrganization=False, canUndoOrganization=False)
        self.enqueue(operation, pin, input_context={'organization_approval':dict(pin)})

    @pyqtSlot()
    def recoverOrganization(self):
        if not self.job: self.enqueue('get_last_organization', {})

    @pyqtSlot(bool)
    def setExpanded(self, value):
        self.presentation.resize(value)
        if not value: self.presentation.open('result')
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
        parsed = parse_pasted_mime_content(clipboard.mimeData(), clipboard.text())
        kind = parsed['kind']
        if kind == 'error':
            self.image_input_error(parsed['error'])
            return {'text':'', 'kind':'none'}
        if kind == 'image':
            self.acceptDroppedImage(parsed['image'], parsed['name'], instruction)
            return {'text':'', 'kind':'image'}
        if kind == 'file_reference':
            self.clearAttachment()
            return {'text':parsed['text'], 'kind':'file_reference'}
        return {'text':parsed['text'], 'kind':kind}

    def image_input_error(self, message):
        self.update(status=message, phase='error', error=True, hasWorkbench=True, expanded=True,
            imageInputSuggested=True, canRetryRequest=False, finderSettingsSuggested=False, translationSettingsSuggested=False)

    def setDropActive(self, value):
        if self._state['dropActive'] != value: self.update(dropActive=value)

    def beginImageReceive(self):
        if self.quitting: return None
        self.presentation.begin_task()
        self.generation += 1; self._receiving_token = self.generation; self.pending = None
        if self.job: self.job.stop.set()
        self.clearAttachment(); self.clearImagePreview(); self.clear_ocr_source()
        self.update(receivingImage=True, busy=True, phase='working', view='notice', error=False,
            text='', meta='', expanded=True, hasWorkbench=True, requestText='Dịch ảnh đang nhận',
            imageInputSuggested=False, finderSettingsSuggested=False, translationSettingsSuggested=False,
            canRetryRequest=False, status='Đang nhận ảnh từ macOS…')
        return self._receiving_token

    def isImageReceiveCurrent(self, token):
        return not self.quitting and token == self._receiving_token and token == self.generation

    def finishImageReceive(self, token, *, image=None, label='', instruction='', error=None):
        if not self.isImageReceiveCurrent(token): return False
        self._receiving_token = None
        self.update(receivingImage=False, busy=self.job is not None)
        if error: self.image_input_error(error); return False
        return self.acceptDroppedImage(image, label, instruction)

    @pyqtSlot('QVariantList', str, result=bool)
    def dropImage(self, urls, instruction=''):
        if self.quitting: return False
        img, name, err = parse_image_url_input(urls, 'dropped')
        if err: self.image_input_error(err); return False
        return self.acceptDroppedImage(img, name, instruction)

    @pyqtSlot(QUrl, str, result=bool)
    def chooseImageFile(self, url, instruction=''):
        if self.quitting: return False
        img, name, err = parse_image_url_input(url, 'selected_file')
        if err: self.image_input_error(err); return False
        return self.acceptDroppedImage(img, name, instruction)

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
            source_language=self._effective_source_language(),
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
        if self.quitting or self.job or self.pending or self._state['busy'] or self._region_previous:
            if not self.quitting: self.update(status='Đợi tác vụ hiện tại hoàn tất.')
            return
        self._region_previous = ({key: self._state[key] for key in REGION_PREVIOUS_FIELDS}, self._retry_request)
        self.presentation.open('result'); self.presentation.resize(False); self.presentation.read()
        self.generation += 1; generation = self.generation; self._capture_position = None

        def begin():
            if self.quitting or generation != self.generation: return
            logging.getLogger(__name__).info('region_capture_dispatching')
            self.enqueue('capture_translate', dict(mode='region', source_language=self._effective_source_language(),
                target_language=self.settings['target_language'], preserve_until_capture=True, look_input=True))
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
        invocation = self.quicklook_journal.invocation_id() if stage == 'selection' else None
        if stage == 'selection': self._received_invocation_id = invocation
        self.quicklook_journal.record(stage, invocation_id=invocation, **metadata)

    def selectionPresented(self):
        if self._presentation_invocation_id:
            self.quicklook_journal.record('presented', invocation_id=self._presentation_invocation_id)
            self._presentation_invocation_id = None

    def restore_selection_view(self):
        if self._selection_return is not None:
            token, self._selection_return = self._selection_return, None
            self.presentation.restore_view(token)

    def _begin_selected_text(self, invocation):
        pid, app_name, err = get_frontmost_app_info()
        if err:
            self.quicklook_journal.record(err, invocation_id=invocation)
            self.summonLook(); return
        if self._selection_return is None:
            self._selection_return = self.presentation.capture_view()
        self._region_previous = ({key: self._state[key] for key in REGION_PREVIOUS_FIELDS}, self._retry_request)
        self.presentation.open('result'); self.presentation.resize(False); self.presentation.read()
        self.update(selectionNotice='', selectionNeedsPermission=False)
        self.enqueue('capture_translate', dict(mode='selection', preserve_until_capture=True,
            look_input=True, source_language=self._effective_source_language(), target_language=self.settings['target_language']),
            input_context={'selection_pid': pid, 'selection_app': app_name, 'quicklook_invocation_id': invocation})
        self._selection_present_generation = self.generation
        self.quicklook_journal.record('capture_requested', invocation_id=invocation, generation=self.generation)

    @pyqtSlot()
    def revealRunningApp(self):
        path = runtime_identity().get('bundle_path')
        if not path: self.update(readinessStatus='Bản source chưa có app bundle để chọn.'); return
        try: subprocess.Popen(['open', '-R', path])
        except OSError: self.update(readinessStatus='Chưa mở được Finder. Đường dẫn app được hiển thị bên dưới.')

    @pyqtSlot()
    def openSelectionAccess(self):
        from rat.os.permissions import open_accessibility_settings
        self.quicklook_journal.record('permission_settings_requested', invocation_id=self._selection_invocation_id)
        if not open_accessibility_settings():
            self.update(selectionNotice='Chưa mở được Cài đặt. Bạn vào Quyền riêng tư & Bảo mật → Trợ năng để cho phép RAT, rồi bôi đen và bấm lại phím tắt.',
                selectionNeedsPermission=True)

    @pyqtSlot()
    def restartHotkey(self): self.hotkeyRestartRequested.emit()

    HISTORY_FIELDS = HISTORY_FIELDS

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
        view = deepcopy({k: getattr(self.presentation, k) for k in fields})
        if self._selection_return and self._selection_return[0] == key:
            view.update(self._selection_return[1])
        title = (values.get('requestText') or values.get('status') or 'Công việc')[:60]
        self._task_history.insert(0, pack_task_history_item(
            key, title, values, view, self._last_image, self._draft_image,
            values.get('imageLabel', ''), self._result_ref, self._ocr_source_ref,
            self._ocr_current_text, self._translation_args, self.finder_artifact, self._next_draft
        ))
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
    def clearTaskHistory(self): self._task_history.clear(); self.update()

    def diagnostic_events(self): return format_diagnostic_events(self.quicklook_journal)

    @pyqtSlot(str)
    def reportDiagnosticError(self, message): self.update(settingsNotice=message)

    @pyqtSlot(str, result=str)
    def exportDiagnostics(self, url):
        err = export_diagnostics_to_file(self.quicklook_journal, url)
        if not err: self.update(settingsNotice='Đã xuất chẩn đoán; không kèm nội dung nguồn.')
        return err

    @pyqtSlot(str, result=str)
    def changeShortcut(self, name):
        if self.job or not self.rebind_hotkey:
            return 'Đợi tác vụ kết thúc trước khi đổi phím tắt.'
        updated, err = change_shortcut_setting(self.settings, name, self.rebind_hotkey)
        if err:
            return err
        self.settings = updated
        self.update()
        return ''

    @pyqtSlot()
    def togglePin(self): self.update(pinned=not self._state['pinned'])

    @pyqtSlot()
    def collapseBubble(self):
        self._selection_present_generation = self._presentation_invocation_id = None
        self.presentation.read(); self.update(bubbleCollapsed=True)

    @pyqtSlot()
    def toggleComposer(self):
        if self._state['bubbleCollapsed']:
            self.update(bubbleCollapsed=False)
            if self._state['hasWorkbench']: return
        self.presentation.composer_visible = not self.presentation.composer_visible
        self.update()
        if self.presentation.composer_visible: self.minimalRequested.emit()

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
            source_language=self._effective_source_language(),
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
        new_task = is_new_task_operation(operation, self._state['phase'], args)
        preserve_region = operation == 'capture_translate' and args.get('mode') in ('region', 'selection') and args.get('preserve_until_capture')
        if new_task and not preserve_region and not self._hold_chat_requested:
            self._hold_chat_requested = False; self.remember_task()
            self._selection_return = self._selection_invocation_id = self._presentation_invocation_id = None
            self._state['selectionNotice'] = ''; self.presentation.begin_task(); self._result_ref = None
        if not preserve_region and (operation in ('find_files', 'capture_translate')
                or (operation == 'submit_goal' and not args.get('source_ref') and self._state['phase'] != 'needs_input')
                or (operation == 'translate_text' and not args.get('source_ref'))):
            self.clear_ocr_source()
        is_file_translate = (operation == 'capture_translate' and args.get('mode') == 'file')
        if new_task and not preserve_region and not is_file_translate: self.finder_artifact = None
        if new_task and not preserve_region: self.organization_artifact = None
        updates = pending_task_initial_updates(operation, args, new_task, preserve_region, is_file_translate,
                                               bool(self.finder_artifact), self.presentation.extent == 'expanded')
        if updates: self.update(**updates)
        session = MiniSession(self.settings, artifact_store=self.session.runtime.artifact_store) if operation == 'check_mini_readiness' or preserve_region else self.session
        job = MiniJob(session, operation, args, query, generation, input_context)
        self.job = job
        def deliver_result(value):
            if job.generation == self.generation: self.render(value)
            elif value.get('invocation_id'):
                self.quicklook_journal.record('discarded_result', invocation_id=value['invocation_id'], generation=job.generation)
        job.result.connect(deliver_result)
        job.progress.connect(lambda message: self.update(status=message) if job.generation == self.generation and operation != 'check_mini_readiness' else None)
        job.captured.connect(lambda source: self.remember_capture_position(job, source))
        job.quicklookStage.connect(lambda event: self.quicklook_journal.record(**event))
        job.finished.connect(lambda: self.finished(job))
        job.start()

    def remember_capture_position(self, job, source):
        if job.generation != self.generation: return
        artifact = source['artifact']
        if job.args.get('mode') == 'selection':
            self.quicklook_journal.record('capture_succeeded', invocation_id=job.input_context.get('quicklook_invocation_id'),
                artifact_id=artifact.id, generation=job.generation)
        if job.args.get('preserve_until_capture'):
            self.remember_task()
            if job.args.get('mode') == 'selection': self._selection_return = None
            self.presentation.begin_task(); self._result_ref = None; self.session.clear_pending()
            self.session = job.session; self.clear_ocr_source(); self.clearImagePreview()
            self.finder_artifact = self.organization_artifact = self._region_previous = None
            self.update(pinned=False, canApplyOrganization=False, canUndoOrganization=False, view='notice',
                finderHits=[], text='', meta='', translationDetails='', translationNotice='',
                sameLanguageNotice='', agentSummary='', agentIncomplete=False,
                requestText='Chữ bôi đen' if job.args.get('mode') == 'selection' else 'Vùng chữ đã chọn')
            region_image = source.get('region_image')
            if region_image:
                self._last_image = region_image
                self.update(imagePreviewUrl=self.image_preview.set_input(region_image), imageLabel='Vùng chữ đã chọn')
        if artifact.payload.get('source_kind') in ('image', 'region') or job.args.get('look_input'):
            self._ocr_source_ref = {'artifact_id': artifact.id, 'revision': artifact.revision}
            self._ocr_current_text = artifact.payload['text']
            self._translation_args = dict(source['translation_args'])
            self.update(**capture_position_ocr_updates(artifact, source, job, self._state['lookSource'], self._state['ocrOriginalText']))
        if job.args.get('mode') == 'region': self._capture_position = QCursor.pos()
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
            stage, reason = render_journal_stage(error, self._region_previous, response)
            self.quicklook_journal.record(stage, invocation_id=invocation, reason=reason,
                execution_id=response.execution_id if response else None)
        if value.get('operation') == 'check_mini_readiness':
            checks = next((a.payload for a in (response.artifacts if response else []) if a.kind == 'mini_readiness'), None)
            self.update(readinessSummary=self.readiness_summary(checks['checks']) if checks else self._state['readinessSummary'],
                readinessBusy=False,
                readiness=checks['checks'] if checks else self._state['readiness'],
                readinessStatus=('Tất cả thành phần đã sẵn sàng.' if checks and checks['status']=='ready' else
                    'Một số chức năng cần xử lý. Bạn vẫn có thể dùng phần đã sẵn sàng.' if checks else 'Chưa kiểm tra được. Hãy thử lại.'))
            if checks and any(c.get('state') == 'action_required' for c in checks.get('checks', [])):
                if not os.environ.get('PYTEST_CURRENT_TEST') and self._state.get('phase') == 'idle' and not self._state.get('hasWorkbench'):
                    self.presentation.open('welcome')
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
            if any(code in str(error) for code in ('source_expired', 'source_integrity_mismatch', 'stale_source_ref')):
                self.presentation.workspace = 'result'
                if self.presentation.surface in ('ocr', 'source'):
                    self.presentation.open('result')
                self.update(canRetryTranslation=False, hasOcrSource=False, canRetryRequest=False)
            flags = render_error_suggestions(str(error))
            self.update(phase='cancelled' if flags['cancelled'] else 'error', error=not flags['cancelled'],
                translationSettingsSuggested=flags['translation_suggested'],
                finderSettingsSuggested=flags['finder_suggested'],
                imageInputSuggested=flags['image_suggested'],
                status=flags['status'])
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
        artifact_res = process_render_artifacts(response.artifacts if response else [], response, model_loop, self._state['agentIncomplete'], self.finder_artifact)
        if artifact_res:
            kind = artifact_res['kind']
            if kind == 'organization':
                self.clear_ocr_source(); self.organization_artifact = artifact_res['artifact']
                self.complete_surface(); self.update(**artifact_res['update']); return
            if kind == 'finder_results':
                self.remember_finder_diagnostic(artifact_res['data']); self.clear_ocr_source()
                self.finder_artifact = artifact_res['artifact']; self.complete_surface()
                self.update(**artifact_res['update']); return
            if kind == 'translation':
                data, artifact = artifact_res['data'], artifact_res['artifact']
                self._result_ref = {'artifact_id': artifact.id, 'revision': artifact.revision}
                source_capture = data.get('source_capture') or {}
                if not source_capture: self.clear_ocr_source()
                elif self._ocr_source_ref == source_capture.get('source_ref'):
                    self._translation_args = {'source_ref': dict(self._ocr_source_ref),
                        'source_language': data['source_language'], 'target_language': data['target_language'],
                        'style': data.get('style', 'faithful')}
                if len(data.get('text', '')) > 480 and self.presentation.extent != 'expanded': self.presentation.resize(True)
                self.complete_surface(); self.update(**artifact_res['update']); return
        if value.get('operation') in ('open_file', 'reveal_file'):
            self.update(phase='result', status='Đã mở file.' if value['operation'] == 'open_file' else 'Đã hiện trong Finder.')
            self.interactionCompleted.emit()
        else:
            self.complete_surface()
            incomplete = model_loop and self._state['agentIncomplete']
            self.update(phase='partial' if incomplete else 'result', view='notice', text=response.answer or '',
                status='Chưa hoàn tất toàn bộ yêu cầu.' if incomplete else 'Đã hoàn tất.')

    def remember_finder_diagnostic(self, data): record_finder_diagnostic(data)

    @staticmethod
    def readiness_summary(checks): return format_readiness_summary(checks)

    @staticmethod
    def friendly_error(error): return format_user_error_message(str(error))

    @pyqtSlot(int)
    def openSelectedHit(self, index): self.file_action(index, 'open_file')

    @pyqtSlot(int)
    def revealSelectedInFinder(self, index): self.file_action(index, 'reveal_file')

    @pyqtSlot(int)
    def translateSelectedHit(self, index):
        artifact = self.finder_artifact
        if self._state['busy'] or not artifact or not 0 <= index < len(artifact.payload['hits']):
            return
        hit = artifact.payload['hits'][index]
        self.update(requestText="Dịch file: " + hit['title'])
        self.enqueue('capture_translate', dict(mode='file', file_path=hit['path'],
            artifact_id=artifact.id, revision=artifact.revision, resource_id=hit['resource_id'],
            look_input=True, source_language=self._effective_source_language(),
            target_language=self.settings['target_language']))

    @pyqtSlot()
    def returnToFinderResults(self):
        if self._state['busy'] or not self.finder_artifact:
            return
        hits = format_finder_return_hits(self.finder_artifact)
        self.update(phase='result', view='finder', finderHits=hits, text='',
            status=f"Đã tìm thấy {len(hits)} mục",
            meta='Chọn một file để mở hoặc hiện trong Finder',
            canReturnToFinder=False)

    def file_action(self, index, operation):
        action = handle_file_action(self.finder_artifact, index, operation, self._state['busy'])
        if action:
            self.enqueue(action[0], action[1])

    @pyqtSlot(int)
    def copySelectedHitPath(self, index):
        hits = self._state.get('finderHits', [])
        if 0 <= index < len(hits):
            path = hits[index].get('path', '')
            if path:
                QGuiApplication.clipboard().setText(path)
                self.update(shortcutAck='Đã sao chép đường dẫn file', status='Đã sao chép đường dẫn file.')
                self.shortcut_ack_timer.start(1800)

    @pyqtSlot()
    def copyResult(self):
        text = self._state['text'] or '\n'.join(h['path'] for h in self._state['finderHits'])
        if text:
            QGuiApplication.clipboard().setText(text)
            if self._state.get('view') == 'translation': self.update(status='Đã sao chép bản dịch')
            else: self.interactionCompleted.emit()

    @pyqtSlot(str)
    def copyLook(self, displayed_text):
        if displayed_text: QGuiApplication.clipboard().setText(displayed_text); self.interactionCompleted.emit()

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
        updated, session, err, scopes_changed, tr_args, retry = save_preferences_settings(
            self.settings, self.session, changes, secret, self._translation_args, self._retry_request,
            keychain_func=keychain_key, save_func=save_settings
        )
        if err:
            return err
        self.settings, self.session, self._translation_args, self._retry_request = updated, session, tr_args, retry
        if scopes_changed:
            self.organization_artifact = None
            self.update(canApplyOrganization=False, canUndoOrganization=False,
                organizationRecoverySuggested=self._state['view'] == 'organization')
        if self._state['translationSettingsSuggested'] and self._state['phase'] == 'error':
            self._state['status'] = 'Đã cập nhật cài đặt. Bấm Thử lại để dịch đoạn chữ đã giữ.'
        self.update(translationSettingsSuggested=False, targetLanguage=updated.get('target_language', 'vi'),
            llmEnabled=bool(updated.get('llm_enabled', False)),
            settingsNotice='Đã lưu cài đặt.' + (' Hãy xem trước lại nếu đã đổi thư mục.' if scopes_changed else ''))
        return ''

    @pyqtSlot()
    def quit(self):
        self.quitting = True; self.cancel(); self.hideRequested.emit()
        if not self.job: QGuiApplication.quit()
