"""Shared headless capture→observed source_ref→translation orchestration.

Clients provide the existing execution service adapter. This module has no Qt,
Mini UI or provider implementation and never executes OCR/HTTP on its own.
"""
from dataclasses import dataclass
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureTranslationResult:
    response: Any
    operation: str
    args: dict
    capture_response: Any


def translation_arguments(session, defaults, query=''):
    """Shared routing of optional language instructions for a pinned source."""
    arguments = dict(defaults)
    if query:
        route = session.router.resolve(query)
        proposed = route.args if route.operation == 'translate_text' else (
            route.input_request.supplied_inputs.get('args', {}) if route.input_request else {})
        arguments.update({k: v for k, v in proposed.items()
                          if k in ('source_language', 'target_language')})
    return arguments


def run_capture_translation(session, capture_args, *, query='', cancel=lambda: False,
                            on_event=None, progress=None, on_captured=None, on_region_image=None, input_context=None, on_selection_geometry=None):
    if cancel():
        raise ValueError('cancelled:capture')
    capture_parameters = {'mode': capture_args['mode']}
    capture = session.execute('capture_text', capture_parameters, cancel=cancel,
        on_event=on_event, progress=progress, input_context={
            'clipboard_text': capture_args.get('clipboard_text'),
            'selection_pid': (input_context or {}).get('selection_pid'),
            'selection_geometry_callback': on_selection_geometry,
            'image_input': capture_args.get('image_input'),
            'image_bytes': capture_args.get('image_bytes'),
            'region_image_callback': on_region_image})
    if capture.error or capture.pending_input_request:
        logger.info('capture_translation_stopped stage=capture')
        return CaptureTranslationResult(capture, 'capture_text', capture_parameters, capture)
    artifact = next((a for a in capture.artifacts if a.kind == 'captured_text'), None)
    if artifact is None:
        raise ValueError('capture_artifact_missing')
    if cancel():
        raise ValueError('cancelled:capture')
    args = translation_arguments(session, {'source_ref': {'artifact_id': artifact.id, 'revision': artifact.revision},
        'source_language': capture_args.get('source_language', 'auto'),
        'target_language': capture_args.get('target_language', 'vi')}, query)
    if on_captured:
        on_captured(artifact, dict(args))
    if cancel():
        raise ValueError('cancelled:translation')
    if capture_args.get('observe_only'):
        # Look supplies observations to the same session. An empty instruction
        # stops at capture; an explicit goal goes through the shared ingress.
        if not query.strip():
            return CaptureTranslationResult(capture, 'capture_text', capture_parameters, capture)
        response = session.submit(query, source_ref=args['source_ref'], cancel=cancel,
                                  on_event=on_event, progress=progress)
        return CaptureTranslationResult(response, 'submit_goal', {'source_ref': args['source_ref']}, capture)
    logger.info('captured_text_translation_started')
    response = session.execute('translate_text', args, query=query, cancel=cancel,
        on_event=on_event, progress=progress)
    return CaptureTranslationResult(response, 'translate_text', args, capture)


def run_corrected_translation(session, source_ref, text, translation_args, *,
                             query='', cancel=lambda: False, on_event=None, progress=None, on_captured=None, observe_only=False):
    """Create a user-edit artifact, then translate it without recapturing/OCR."""
    if cancel():
        raise ValueError('cancelled:correction')
    edit_args = {'source_ref': dict(source_ref), 'text': text}
    correction = session.execute('correct_captured_text', edit_args, cancel=cancel,
        on_event=on_event, progress=progress)
    if correction.error or correction.pending_input_request:
        return CaptureTranslationResult(correction, 'correct_captured_text', edit_args, correction)
    artifact = next((a for a in correction.artifacts if a.kind == 'captured_text'), None)
    if artifact is None:
        raise ValueError('capture_artifact_missing')
    args = translation_arguments(session,
        {k:v for k,v in translation_args.items() if k in ('source_language','target_language','style')}, query)
    args['source_ref'] = {'artifact_id': artifact.id, 'revision': artifact.revision}
    if cancel():
        raise ValueError('cancelled:translation')
    if on_captured:
        on_captured(artifact, dict(args))
    if cancel():
        raise ValueError('cancelled:translation')
    if observe_only:
        response = session.submit(query, source_ref=args['source_ref'], cancel=cancel,
                                  on_event=on_event, progress=progress) if query.strip() else correction
        return CaptureTranslationResult(response, 'submit_goal' if query.strip() else 'capture_text', args, correction)
    response = session.execute('translate_text', args, query=query, cancel=cancel, on_event=on_event, progress=progress)
    return CaptureTranslationResult(response, 'translate_text', args, correction)
