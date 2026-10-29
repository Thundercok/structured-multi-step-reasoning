"""Asynchronous projection adapter; every business action uses AgentExecutionService."""
import json
import logging
import os
from pathlib import Path
import threading
from PyQt6.QtCore import QThread, pyqtSignal
from rat.ui.mini_diagnostics import write_diagnostic
from rat.engine.capture_translation import run_capture_translation, run_corrected_translation, translation_arguments

logger = logging.getLogger(__name__)

class MiniJob(QThread):
    result = pyqtSignal(object)
    progress = pyqtSignal(str)
    captured = pyqtSignal(object)

    def __init__(self, session, operation, args, query, generation, input_context=None):
        super().__init__()
        self.session, self.operation, self.args, self.query = session, operation, args, query
        self.generation, self.stop = generation, threading.Event()
        self.input_context = dict(input_context or {})

    def run(self):
        events = []
        write_diagnostic('execution-status.json', dict(state='started', operation=self.operation, generation=self.generation))
        try:
            progress = lambda text: self.progress.emit(text)
            def observed_step(step):
                # Only public tool receipts/checks, never thought/raw completion.
                labels = {'find_files': 'tìm file', 'translate_text': 'dịch',
                    'plan_folder_organization': 'lập bản xem trước',
                    'capture_text': 'đọc chữ trong ảnh'}
                if step.tool_name in labels and step.tool_result is not None:
                    failed = step.error or (isinstance(step.tool_result, dict) and step.tool_result.get('error'))
                    waiting = isinstance(step.tool_result, dict) and step.tool_result.get('status') == 'needs_input'
                    checked = any(r.get('status') == 'PASS' for r in step.verification)
                    self.progress.emit(('Cần bổ sung dữ kiện: ' if waiting else 'Chưa hoàn tất: ' if failed else 'Đã thực hiện: ') +
                        labels[step.tool_name] + (' · đã đối chiếu cấu trúc' if checked and not failed and not waiting else ''))
            operation, args = self.operation, self.args
            capture_response = None
            if operation == 'capture_translate':
                region_image = {}
                outcome = run_capture_translation(self.session, args, query=self.query,
                    input_context=self.input_context,
                    cancel=self.stop.is_set, on_event=lambda event: events.append(event.to_dict()),
                    on_region_image=lambda image: region_image.update(image=image),
                    progress=progress, on_captured=lambda artifact, arguments:
                        self.captured.emit({'artifact':artifact, 'translation_args':arguments,
                                            'region_image':region_image.get('image')}))
                response, operation, args = outcome.response, outcome.operation, outcome.args
                capture_response = outcome.capture_response
            elif operation == 'correct_translate':
                outcome = run_corrected_translation(self.session, args['source_ref'], args['text'],
                    args['translation_args'], query=self.query, cancel=self.stop.is_set,
                    observe_only=bool(args.get('observe_only')),
                    on_event=lambda event: events.append(event.to_dict()), progress=progress,
                    on_captured=lambda artifact, arguments:
                        self.captured.emit({'artifact':artifact, 'translation_args':arguments}))
                response, operation, args = outcome.response, outcome.operation, outcome.args
                capture_response = outcome.capture_response
            elif operation == 'submit_goal':
                response = self.session.submit(self.query, input_kind=self.args.get('input_kind','typed'), cancel=self.stop.is_set,
                    on_event=lambda event: events.append(event.to_dict()), progress=progress, on_step=observed_step,
                    source_ref=self.args.get('source_ref'))
            else:
                if operation == 'translate_text' and args.get('source_ref'):
                    args = translation_arguments(self.session, args, self.query)
                response = self.session.execute(operation, args, query=self.query, cancel=self.stop.is_set, input_context=self.input_context,
                    on_event=lambda event: events.append(event.to_dict()), progress=progress)
            value = {'response': response, 'events': events, 'operation': operation,
                     'capture_verification': capture_response.verification_reports if capture_response else [],
                     'llm_calls': self.session.client.calls,
                     'capture_mode':self.args.get('mode') if self.operation == 'capture_translate' else None}
            if self.operation == 'capture_translate':
                logger.info('captured_text_translation_finished status=%s', 'error' if response.error else response.completion_status)
            receipt_written = False
            try:
                recording = os.environ.get('RAT_MINI_ACCEPTANCE_DIR')
                if recording:
                    folder = Path(recording)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / (response.execution_id + '.json')).write_text(json.dumps({
                        'query': self.query, 'operation': operation, 'args': args,
                        'answer': response.answer, 'error': response.error, 'events': events,
                        'artifacts': [a.to_dict() for a in response.artifacts],
                        'capture_artifacts': [a.to_dict() for a in capture_response.artifacts] if capture_response else [],
                        'capture_verification': value['capture_verification'],
                        'verification': response.verification_reports, 'llm_calls': self.session.client.calls,
                        'execution_path': (response.qa_telemetry or {}).get('mini_execution_path'),
                        'controller_decisions': response.controller_decisions,
                        'completion_status': response.completion_status,
                        'steps': [{'number': step.step_number, 'operation': step.tool_name,
                                   'error': step.error, 'verification': step.verification}
                                  for step in response.steps],
                        'usage_unknown': self.session.client.usage_unknown}, ensure_ascii=False, default=str, indent=2))
                receipt_written = bool(recording)
            except Exception as recording_error:
                value['recording_error'] = type(recording_error).__name__
                logger.warning('acceptance_recording_failed type=%s', type(recording_error).__name__)
            write_diagnostic('execution-status.json', dict(state='finished', operation=operation,
                generation=self.generation, execution_id=response.execution_id,
                completion_status=response.completion_status, receipt_written=receipt_written,
                recording_error=value.get('recording_error'), tool_error=bool(response.error)))
            self.result.emit(value)
        except Exception as exc:
            write_diagnostic('execution-status.json', dict(state='failed', operation=self.operation,
                generation=self.generation, exception_type=type(exc).__name__))
            self.result.emit({'error': str(exc), 'events': events, 'operation':self.operation,
                'capture_mode':self.args.get('mode') if self.operation == 'capture_translate' else None})
