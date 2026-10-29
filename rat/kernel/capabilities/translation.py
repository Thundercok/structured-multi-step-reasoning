"""Shared translation reasoning tools; UI and Agent have exactly one implementation."""
import hashlib
import copy
import re
import time

from rat.kernel.capabilities.observed_source import observed_capture
from rat.kernel.contracts import InputRequest
from rat.kernel.registry import Capability, OperationDefinition
from rat.engine.snippet_translation import capture_text
from rat.engine.verification import VerificationReport, VerificationStatus
from rat.kernel.input_context import IMAGE_ORIGINS, MAX_IMAGE_BYTES
from rat.engine.ocr_paragraphs import POLICY, apply_line_joins


class CaptureVerifier:
    def check_execution(self, evidence):
        data = evidence.result
        text = data.get('text') if isinstance(data, dict) else None
        okay = (isinstance(text, str) and bool(text.strip()) and len(text) <= 8000
            and data.get('source_sha256') == hashlib.sha256(text.encode()).hexdigest()
            and data.get('source_kind') == evidence.args.get('mode'))
        checked = ['captured_text_hash', 'capture_mode', 'snippet_limit']
        if okay and 'ocr_normalization' in data:
            try:
                raw, preparation = data['ocr_raw_text'], data['ocr_normalization']
                okay = (preparation['policy'] == POLICY
                    and preparation['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
                    and preparation['text_sha256'] == data['source_sha256']
                    and apply_line_joins(raw, preparation['joined_line_indexes']) == text)
            except (KeyError, TypeError, ValueError):
                okay = False
            checked.append('ocr_soft_wrap_derivation')
        if okay and (data['source_kind'] == 'image' or
                     (data['source_kind'] == 'region' and data.get('input_provenance') is not None)):
            source = data.get('input_provenance')
            okay = (isinstance(source, dict) and source.get('version') == 1
                and source.get('kind') == 'image' and source.get('origin') in IMAGE_ORIGINS
                and isinstance(source.get('input_id'), str) and bool(source['input_id'])
                and isinstance(source.get('content_sha256'), str)
                and re.fullmatch('[0-9a-f]{64}', source['content_sha256']) is not None
                and type(source.get('byte_count')) is int and 0 < source['byte_count'] <= MAX_IMAGE_BYTES)
            checked.append('image_provenance_structure')
        return VerificationReport(VerificationStatus.PASS if okay else VerificationStatus.FAIL,
            'capture_structure', 'Đối chiếu cấu trúc và hash; chưa xác nhận OCR đọc đúng ảnh.',
            (evidence.id,), checked=tuple(checked))

    def check_answer(self, goal, answer, evidence):
        return None


class TranslationVerifier:
    def check_execution(self, evidence):
        data = evidence.result
        okay = isinstance(data, dict) and data.get('source_sha256') == hashlib.sha256(data.get('source_text', '').encode()).hexdigest()
        if okay:
            cursor = 0
            for segment in data.get('segments', []):
                okay &= segment['source_start'] == cursor and segment['source_end'] > cursor
                cursor = segment['source_end']
            okay &= cursor == len(data.get('source_text', ''))
        if okay and evidence.args.get('source_ref'):
            source = data.get('source_capture')
            okay = (isinstance(source, dict) and source.get('source_ref') == evidence.args['source_ref']
                and source.get('text_sha256') == data.get('source_sha256'))
        local = isinstance(data, dict) and 'offline_argos' in data.get('provider', '').split(', ')
        if okay and local:
            model = data.get('local_model')
            okay = (isinstance(model, dict)
                and model.get('id') == data.get('source_language', '')+'-'+data.get('target_language', '')
                and isinstance(model.get('package_sha256'), str)
                and re.fullmatch('[0-9a-f]{64}', model['package_sha256']) is not None
                and model.get('device') == 'cpu')
        status = VerificationStatus.FAIL if not okay else VerificationStatus.UNKNOWN if data.get('status') == 'partial' else VerificationStatus.PASS
        return VerificationReport(status, 'translation_structure',
            'Kiểm tra hash và độ phủ đoạn; chưa xác nhận bản dịch đúng nghĩa.', (evidence.id,),
            checked=('source_hash', 'segment_coverage') +
                (('capture_source_ref',) if evidence.args.get('source_ref') else ()) +
                (('local_model_provenance',) if local else ()))

    def check_answer(self, goal, answer, evidence):
        return None


class CaptureCorrectionVerifier:
    def check_execution(self, evidence):
        data = evidence.result
        text = data.get('text') if isinstance(data, dict) else None
        correction = data.get('correction') if isinstance(data, dict) else None
        okay = (isinstance(text, str) and text == evidence.args.get('text') and bool(text.strip())
            and len(text) <= 8000 and data.get('text_origin') == 'user_edit'
            and data.get('source_sha256') == hashlib.sha256(text.encode()).hexdigest()
            and isinstance(correction, dict) and correction.get('parent_ref') == evidence.args.get('source_ref')
            and isinstance(correction.get('parent_text_sha256'), str)
            and re.fullmatch('[0-9a-f]{64}', correction['parent_text_sha256']) is not None)
        return VerificationReport(VerificationStatus.PASS if okay else VerificationStatus.FAIL,
            'capture_correction_structure', 'Đối chiếu chữ người dùng sửa và liên kết nguồn; không xác nhận nội dung đúng nghĩa.',
            (evidence.id,), checked=('user_text_hash', 'parent_source_ref'))

    def check_answer(self, goal, answer, evidence):
        return None


def create_translation_capability(translator):
    cap = Capability('translation', 'Dịch đoạn văn', 'Dịch văn bản nhập, clipboard hoặc OCR vùng chọn.')
    ref = {'type': 'object', 'additionalProperties': False, 'properties': {
        'artifact_id': {'type': 'string', 'maxLength': 128}, 'revision': {'type': 'integer', 'minimum': 1}},
        'required': ['artifact_id', 'revision']}

    capture_contract = {'type': 'object', 'properties': {
            'text': {'type':'string', 'minLength':1, 'maxLength':8000},
            'source_kind': {'type':'string', 'enum':['clipboard','selection','region','image']},
            'source_sha256': {'type':'string', 'pattern':'^[0-9a-f]{64}$'},
            'captured_at': {'type':'number'},
            'language_hint': {'type':['string','null']},
            'ocr_raw_text': {'type':'string', 'maxLength':8000},
            'ocr_normalization': {'type':'object', 'properties':{
                'policy': {'const': POLICY},
                'joined_line_indexes': {'type':'array', 'maxItems':8000, 'items':{'type':'integer','minimum':0}},
                'raw_sha256': {'type':'string','pattern':'^[0-9a-f]{64}$'},
                'text_sha256': {'type':'string','pattern':'^[0-9a-f]{64}$'}},
                'required':['policy','joined_line_indexes','raw_sha256','text_sha256']},
            'input_provenance': {'type':'object', 'properties': {
                'version': {'type':'integer', 'const':1}, 'kind': {'const':'image'},
                'input_id': {'type':'string', 'pattern':'^img-[0-9a-f]{32}$'},
                'origin': {'type':'string', 'enum':sorted(IMAGE_ORIGINS)},
                'content_sha256': {'type':'string', 'pattern':'^[0-9a-f]{64}$'},
                'byte_count': {'type':'integer', 'minimum':1, 'maximum':MAX_IMAGE_BYTES},
                'source_file_sha256': {'type':['string','null'], 'pattern':'^[0-9a-f]{64}$'}},
                'required':['version','kind','input_id','origin','content_sha256','byte_count']}},
            'required':['text','source_kind','source_sha256','captured_at'],
            'allOf':[{'if':{'properties':{'source_kind':{'const':'image'}}},
                'then':{'required':['input_provenance']}}]}

    def correct_capture(args, **context):
        if not context.get('user_initiated'):
            raise ValueError('correction_requires_user_action')
        if not args['text'].strip():
            raise ValueError('empty_corrected_text')
        parent = observed_capture(args['source_ref'], context)
        result = copy.deepcopy(parent.payload)
        # The old preparation describes the parent OCR text, not this edit.
        # Its artifact remains pinned by parent_ref; never relabel an edit as
        # the deterministic output of OCR soft-wrap joining.
        result.pop('ocr_normalization', None)
        previous = result.get('correction') or {}
        result.update(text=args['text'], text_origin='user_edit', language_hint=None,
            source_sha256=hashlib.sha256(args['text'].encode()).hexdigest(),
            correction={'parent_ref': copy.deepcopy(args['source_ref']),
                'parent_text_sha256': parent.payload['source_sha256'],
                'root_source_ref': copy.deepcopy(previous.get('root_source_ref') or args['source_ref']),
                'original_text_sha256': previous.get('original_text_sha256') or parent.payload['source_sha256'],
                'edited_at': time.time()})
        return result

    correction_contract = copy.deepcopy(capture_contract)
    correction_contract['properties'].update({
        'text_origin': {'type': 'string', 'enum': ['user_edit']},
        'correction': {'type': 'object', 'properties': {
            'parent_ref': ref, 'root_source_ref': ref,
            'parent_text_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
            'original_text_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
            'edited_at': {'type': 'number'}},
            'required': ['parent_ref', 'root_source_ref', 'parent_text_sha256', 'original_text_sha256', 'edited_at']}})
    correction_contract['required'] += ['text_origin', 'correction']

    cap.register_operation(OperationDefinition('correct_captured_text',
        'Record an explicit user correction as a new captured-text artifact; preserve the original.',
        {'type':'object', 'additionalProperties':False, 'properties':{
            'source_ref':ref, 'text':{'type':'string','minLength':1,'maxLength':8000}},
            'required':['source_ref','text']}, correct_capture, artifact_kind='captured_text',
        result_contract=correction_contract,
        verifier=CaptureCorrectionVerifier(), model_visible=False))

    def translate(args, **context):
        if bool(args.get('text')) == bool(args.get('source_ref')):
            return InputRequest('translate_text', supplied_inputs=args,
                missing_fields=[{'name': 'text', 'required': True}], prompt='Nhập văn bản hoặc lấy chữ từ clipboard/vùng màn hình.')
        text = args.get('text')
        source_capture = None
        if args.get('source_ref'):
            pin = args['source_ref']
            artifact = observed_capture(pin, context)
            text = artifact.payload['text']
            digest = artifact.payload['source_sha256']
            source_capture = {'source_ref': dict(pin), 'source_kind': artifact.payload['source_kind'],
                'text_sha256': digest,
                'text_origin': artifact.payload.get('text_origin', 'ocr' if artifact.payload['source_kind'] in ('image','region') else 'captured_text'),
                'correction': copy.deepcopy(artifact.payload.get('correction')),
                'ocr_normalization': copy.deepcopy(artifact.payload.get('ocr_normalization')),
                'input_provenance': copy.deepcopy(artifact.payload.get('input_provenance'))}
        result = translator.translate(text, args.get('source_language', 'auto'), args.get('target_language', 'vi'),
                                      context.get('should_cancel') or (lambda: False))
        if result.get('needs_language'):
            return InputRequest('translate_text', supplied_inputs=args,
                missing_fields=[{'name': 'source_language', 'required': True}],
                prompt='Chưa xác định chắc ngôn ngữ nguồn. Hãy chọn ngôn ngữ rồi dịch lại.')
        if source_capture is not None:
            result['source_capture'] = source_capture
        return result

    cap.register_operation(OperationDefinition('translate_text', 'Translate a snippet; prefer an observed capture source_ref to preserve original text.',
        {'type': 'object', 'additionalProperties': False, 'properties': {
            'text': {'type': 'string', 'maxLength': 8000}, 'source_ref': ref,
            'source_language': {'type': 'string', 'maxLength': 35},
            'target_language': {'type': 'string', 'maxLength': 35},
            'style': {'type': 'string', 'enum': ['faithful', 'plain']}}, 'required': []},
        translate, artifact_kind='translation', verifier=TranslationVerifier(),
        observation_formatter=lambda data: {k: data.get(k) for k in
            ('status', 'text', 'provider', 'source_language', 'target_language', 'warnings', 'source_capture', 'local_model')}))

    def capture(args, **context):
        if not context.get('user_initiated'):
            raise ValueError('capture_requires_user_action')
        return capture_text(args['mode'], context.get('should_cancel') or (lambda: False),
            context.get('clipboard_text'), context.get('image_bytes'), context.get('image_input'),
            context.get('region_image_callback'), context.get('selection_pid'), context.get('selection_geometry_callback'))
    cap.register_operation(OperationDefinition('capture_text', 'Capture text after an explicit user action.',
        {'type': 'object', 'properties': {'mode': {'type': 'string', 'enum': ['clipboard', 'selection', 'region', 'image']}},
         'required': ['mode'], 'additionalProperties': False}, capture, artifact_kind='captured_text',
        result_contract=capture_contract,
        verifier=CaptureVerifier(), model_visible=False))
    return cap
