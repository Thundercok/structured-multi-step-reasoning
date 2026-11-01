"""Pure projections from RAT Lite controller state and artifacts to QML-facing dicts."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from rat.os.hotkey_chords import DEFAULT_CHORD, chord
from rat.os.permissions import runtime_identity


REGION_PREVIOUS_FIELDS = (
    'phase', 'status', 'error', 'expanded', 'hasWorkbench', 'view',
    'agentSummary', 'agentIncomplete', 'settingsNotice', 'lastOperation',
    'translationSettingsSuggested', 'finderSettingsSuggested', 'imageInputSuggested',
    'canRetryRequest'
)


HISTORY_FIELDS = (
    'view', 'phase', 'status', 'error', 'text', 'meta', 'requestText',
    'hasWorkbench', 'pinned', 'attachmentLabel', 'finderHits', 'hasOcrSource', 'ocrText',
    'ocrCommittedText', 'ocrOriginalText', 'ocrPreparationNotice', 'captureSourceKind',
    'captureSourceApp', 'lookSource', 'translationDetails', 'translationNotice',
    'sameLanguageNotice',
    'agentSummary', 'agentIncomplete', 'lastOperation'
)


def default_controller_state(settings: dict) -> dict:
    """Khởi tạo toàn bộ từ điển trạng thái UI mặc định của RAT Lite."""
    return dict(
        draftText='', editingRequest=False, settingsNotice='', lastOperation='',
        readinessSummary=[], agentSummary='', agentIncomplete=False,
        lookSource=False, hotkeyStatus='', sameLanguageNotice='', phase='idle', busy=False,
        bubbleCollapsed=False, expanded=False, selectionNotice='', selectionNeedsPermission=False,
        captureSourceApp='', captureSourceKind='', hotkeyStarting=False, shortcutAck='', pinned=False,
        hasWorkbench=False, view='idle', finderHits=[], text='', meta='', canReturnToFinder=False,
        status='Bạn muốn Chuột giúp gì?', requestText='', attachmentLabel='', error=False,
        ocrText='', ocrOriginalText='', ocrCommittedText='', hasOcrSource=False, canRetryTranslation=False,
        translationDetails='', translationNotice='', translationSettingsSuggested=False,
        dropActive=False, receivingImage=False, imagePreviewUrl='', imageLabel='',
        ocrPreparationNotice='', canRetryRequest=False, finderSettingsSuggested=False,
        imageInputSuggested=False, translationDirection='', sourceText='', intentChoice=False, indexProgress='',
        # There is no setup screen; features ask for permissions when first used.
        setupCompleted=True,
        targetLanguage=settings.get('target_language', 'vi'),
        llmEnabled=bool(settings.get('llm_enabled', False)),
        readiness=[], readinessBusy=False, readinessStatus=""
    )


def build_controller_snapshot(state: dict, pres_snapshot: dict, settings: dict, task_history: list, diagnostic_events: list) -> dict:
    combined = dict(state, **pres_snapshot)
    return dict(
        combined,
        lookStatusLabel='Đang xử lý' if state['busy'] else 'Sẵn sàng',
        runningBundlePath=runtime_identity().get('bundle_path') or '',
        accessibilityReady=any(c.get('key') == 'accessibility' and c.get('state') in ('ready', 'not_required') for c in state['readiness']),
        shortcutLabel=chord(settings.get('hotkey_chord', DEFAULT_CHORD))[2],
        taskHistory=[dict(index=i, title=item['title']) for i, item in enumerate(task_history)],
        diagnosticEvents=diagnostic_events,
        ocrDirty=bool(state["hasOcrSource"]) and state["ocrText"] != state["ocrCommittedText"]
    )


def pack_task_history_item(key, title, state: dict, presentation_view: dict, last_image, draft_image,
                            image_label, result_ref, source_ref, source_text: str, translation_args,
                            finder_artifact, draft: str) -> dict:
    """Đóng gói snapshot của tác vụ vào lịch sử để khôi phục khi cần."""
    return dict(
        task_id=key,
        title=title,
        state=deepcopy({k: state[k] for k in HISTORY_FIELDS if k in state}),
        presentation=presentation_view,
        last_image=last_image,
        draft_image=draft_image,
        image_label=image_label,
        result_ref=deepcopy(result_ref),
        source_ref=deepcopy(source_ref),
        source_text=source_text,
        translation_args=deepcopy(translation_args),
        finder=finder_artifact,
        draft=draft
    )


def is_new_task_operation(operation: str, phase: str, args: dict) -> bool:
    """Xác định xem thao tác tiếp theo có bắt đầu một task hoàn toàn mới không."""
    return bool(
        operation in ('find_files', 'capture_translate')
        or (operation == 'submit_goal' and phase != 'needs_input' and not args.get('source_ref'))
        or (operation == 'translate_text' and not args.get('source_ref'))
    )


def pending_task_initial_updates(operation: str, args: dict, new_task: bool, preserve_region: bool,
                                 is_file_translate: bool, has_finder: bool, extent_expanded: bool) -> dict:
    """Tập hợp toàn bộ các trường update khi chuẩn bị chạy một job mới."""
    updates = {}
    if new_task and not preserve_region:
        updates.update(pinned=False, canReturnToFinder=False)
        if not (is_file_translate and has_finder):
            updates.update(view='notice', finderHits=[], text='', meta='', translationDetails='',
                           translationNotice='', sameLanguageNotice='')
        else:
            updates.update(text='', meta='', translationDetails='', translationNotice='', sameLanguageNotice='')
    if operation != "check_mini_readiness":
        updates.update(
            busy=True, phase='working', expanded=extent_expanded, hasWorkbench=True,
            agentSummary='', agentIncomplete=False, lastOperation=operation, error=False,
            translationSettingsSuggested=False, finderSettingsSuggested=False,
            imageInputSuggested=False, status=initial_operation_status(operation, args)
        )
    elif operation == "check_mini_readiness":
        updates['busy'] = True
    return updates


def initial_operation_status(operation: str, args: dict) -> str:
    """Trạng thái ban đầu khi bắt đầu thực thi một tác vụ Mini."""
    capture_status = {
        'selection': 'Đang nhận chữ bôi đen…', 'region': 'Kéo chọn vùng chữ trên màn hình…',
        'image': 'Đang đọc chữ trong ảnh…', 'clipboard': 'Đang đọc Clipboard và dịch…',
        'file': 'Đang đọc file và dịch…'
    }.get(args.get('mode'), 'Đang nhận chữ…')
    return {
        'find_files': 'Đang tìm trong thư mục đã chọn…',
        'translate_text': 'Đang dịch…',
        'capture_translate': capture_status,
        'correct_translate': 'Đang ghi nhận chữ đã sửa và dịch lại…',
        'open_file': 'Đang mở file…',
        'reveal_file': 'Đang hiện trong Finder…'
    }.get(operation, 'Đang thực hiện…')


def capture_position_ocr_updates(artifact, source: dict, job, current_look_source: bool, current_ocr_original: str) -> dict:
    """Trích xuất trường cập nhật OCR và trạng thái nguồn khi bắt được văn bản."""
    raw_ocr = artifact.payload.get('ocr_raw_text', artifact.payload['text'])
    is_joined = bool((artifact.payload.get('ocr_normalization') or {}).get('joined_line_indexes'))
    return dict(
        ocrText=artifact.payload['text'],
        ocrCommittedText=artifact.payload['text'],
        captureSourceKind=artifact.payload['source_kind'],
        captureSourceApp=job.input_context.get('selection_app', '') if artifact.payload['source_kind'] == 'selection' else '',
        lookSource=bool(job.args.get('look_input')) or current_look_source,
        hasOcrSource=True,
        canRetryTranslation=True,
        ocrOriginalText=current_ocr_original if job.operation == 'correct_translate' else raw_ocr,
        ocrPreparationNotice='Đã nối các dòng chữ cùng đoạn để dịch. Chữ nhận ban đầu vẫn được giữ.' if is_joined else ''
    )


def process_render_artifacts(artifacts: list, response, model_loop: bool, is_agent_incomplete: bool, finder_artifact) -> dict | None:
    """Xử lý danh sách artifact trả về từ response và sinh gói cập nhật UI tương ứng."""
    for artifact in reversed(artifacts):
        data = artifact.payload
        if artifact.kind == 'finder_results':
            hits = [dict(hit, kind='file', is_pdf=Path(hit['path']).suffix.lower() == '.pdf',
                         display_path=format_compact_display_path(hit['path']), folder=format_folder_label(hit['path']), match_reason='Spotlight') for hit in data['hits']]
            partial = data.get('status') == 'partial' or bool(data.get('provider_errors'))
            status = f"Tìm thấy {len(hits)} file" if hits else 'Chưa thấy file nào khớp. Thử tả nội dung khác, ví dụ “slide môn NLP tuần trước”.'
            if partial:
                done, total = data.get('coverage', {}).get('completed_roots'), data.get('coverage', {}).get('roots')
                status = ('Spotlight chưa tìm xong. Chưa thể kết luận có file hay không.' if not hits
                          else status + (f' · Đã tìm xong {done}/{total} thư mục.' if done is not None and total else ' · Một số thư mục chưa tìm xong.'))
            if any(e.get('code') == 'spotlight_permission_denied' for e in data.get('provider_errors', [])):
                status += ' macOS chưa cho RAT đọc một số thư mục đã chọn.'
            return dict(
                kind='finder_results', artifact=artifact, data=data,
                update=dict(
                    phase='partial' if partial or (model_loop and is_agent_incomplete) else 'result',
                    view='finder', finderHits=hits, finderSettingsSuggested=partial or not hits,
                    text='', meta='Chọn một file để mở hoặc hiện trong Finder', status=status
                )
            )
        if artifact.kind == 'translation':
            view_data = format_translation_artifact_view(data, finder_artifact_present=bool(finder_artifact))
            return dict(
                kind='translation', artifact=artifact, data=data,
                update=dict(
                    phase='partial' if view_data['partial'] or (model_loop and is_agent_incomplete) else 'result',
                    view='translation', finderHits=[], text=data['text'], meta=view_data['meta'], translationDirection=view_data['direction'], sourceText=data.get('source_text', ''),
                    translationDetails=view_data['details'], translationNotice=view_data['notice'],
                    sameLanguageNotice=view_data['same_language_notice'], status=view_data['status'],
                    canReturnToFinder=view_data['can_return']
                )
            )
    return None


def format_folder_label(raw_path: str) -> str:
    """Thư mục chứa file, rút gọn theo thư mục người dùng: 'Documents/HK1'."""
    try:
        parent = Path(raw_path).resolve().parent
        try:
            return str(parent.relative_to(Path.home().resolve())) or '~'
        except ValueError:
            return str(parent)
    except Exception:
        return ''


def format_compact_display_path(raw_path: str) -> str:
    """Rút gọn str(Path.home()) thành ~ và trả về '<Tên thư mục cha> · ~/...'>."""
    if not raw_path:
        return ""
    try:
        p = Path(raw_path).resolve()
        home = Path.home().resolve()
        try:
            rel = p.relative_to(home)
            short_path = f"~/{rel}"
        except (ValueError, RuntimeError):
            short_path = str(p)
        parent_name = p.parent.name or str(p.parent)
        return f"{parent_name} · {short_path}"
    except Exception:
        return str(raw_path)


def format_finder_return_hits(artifact) -> list[dict]:
    raw_hits = artifact.payload.get('hits', []) if artifact else []
    return [dict(hit, kind='file', is_pdf=Path(hit['path']).suffix.lower() == '.pdf',
                 display_path=format_compact_display_path(hit['path']), folder=format_folder_label(hit['path']), match_reason='Spotlight')
            for hit in raw_hits]


def handle_file_action(artifact, index: int, operation: str, busy: bool) -> tuple[str, dict] | None:
    if busy or not artifact or not 0 <= index < len(artifact.payload.get('hits', [])):
        return None
    hit = artifact.payload['hits'][index]
    return operation, dict(artifact_id=artifact.id, revision=artifact.revision, resource_id=hit['resource_id'])


def format_translation_artifact_view(data: dict, finder_artifact_present: bool = False) -> dict:
    """Format meta, details, notice, same_language_notice, can_return, partial for translation view."""
    languages = {
        'vi': 'Tiếng Việt', 'en': 'Tiếng Anh', 'ja': 'Tiếng Nhật', 'ko': 'Tiếng Hàn',
        'zh': 'Tiếng Trung', 'fr': 'Tiếng Pháp', 'de': 'Tiếng Đức', 'es': 'Tiếng Tây Ban Nha',
        'auto': 'Tự nhận diện'
    }
    src_lang = data.get('source_language', '')
    tgt_lang = data.get('target_language', '')
    direction = f"{languages.get(src_lang, src_lang)} → {languages.get(tgt_lang, tgt_lang)}"
    meta = 'Dịch trên máy' if data.get('local_model') else direction
    provenance = (data.get('source_capture') or {}).get('input_provenance') or {}
    origin = {
        'selected_file': 'Ảnh đã chọn', 'dropped_file': 'Ảnh kéo thả',
        'dropped_image': 'Ảnh kéo thả', 'clipboard_file': 'File ảnh đã dán',
        'clipboard_image': 'Ảnh đã dán'
    }.get(provenance.get('origin'))
    if origin:
        meta = origin + ' · ' + meta
    if (data.get('source_capture') or {}).get('text_origin') == 'user_edit':
        meta = 'Chữ đã sửa · ' + meta
    provider_name = 'OPUS-MT / Argos · trên máy' if data.get('provider') == 'offline_argos' else data.get('provider', '')
    details = f"Dịch vụ: {provider_name}\n" + '\n'.join(data.get('warnings', []))
    notice = '\n'.join(w for w in data.get('warnings', []) if not w.startswith('Đã dùng MyMemory'))
    if data.get('provider') == 'same_language':
        meta += ' · Nội dung đã ở ngôn ngữ đích'
    if provenance.get('kind') == 'file' and provenance.get('file_name'):
        meta = f"{provenance['file_name']} · {meta}"
    can_return = bool(finder_artifact_present and provenance.get('kind') == 'file')
    partial = data.get('status') == 'partial'
    same_lang_msg = (
        'Đoạn này đã là ' + languages.get(tgt_lang, tgt_lang) + '.'
        if data.get('provider') == 'same_language' else ''
    )
    return {
        'meta': meta,
        'direction': direction,
        'details': details.strip(),
        'notice': notice,
        'same_language_notice': same_lang_msg,
        'can_return': can_return,
        'partial': partial,
        'status': 'Chưa dịch hết văn bản' if partial else 'Bản dịch',
    }


def format_readiness_summary(checks: list) -> list:
    """Group individual component checks into 3 headline readiness rows."""
    by_key = {item['key']: item for item in checks}
    groups = [
        ('translation', 'Dịch Anh ↔ Việt', ('ctranslate2', 'sentencepiece', 'en-vi', 'vi-en', 'models')),
        ('image', 'Dịch ảnh', ('Vision',)),
        ('finder', 'Tìm file', ('spotlight', 'folders'))
    ]
    ready_details = {
        'translation': 'Dịch tức thì trên máy, không cần mạng.',
        'image': 'Nhận diện chữ trong ảnh bằng Apple Vision.',
        'finder': 'Tìm file nhanh chóng qua Spotlight macOS.'
    }
    summaries = []
    for key, label, members in groups:
        items = [by_key[name] for name in members if name in by_key]
        state = 'action_required' if any(x['state'] == 'action_required' for x in items) else 'unverified' if not items or any(x['state'] == 'unverified' for x in items) else 'ready'
        detail = ' · '.join(x['detail'] for x in items if x['state'] == 'action_required') or (
            ready_details.get(key, 'Sẵn sàng hoạt động trên máy.') if state == 'ready' else 'Sẵn sàng dùng; quyền truy cập sẽ được hỏi khi cần.'
        )
        summaries.append(dict(key=key, label=label, state=state, detail=detail))
    return summaries


def render_journal_stage(error, region_previous, response) -> tuple[str, str | None]:
    """Xác định stage và reason an toàn để ghi journal."""
    stage = ('capture_failed' if error and region_previous is not None else 'translation_failed' if error
             else 'needs_input' if response and response.pending_input_request else 'execution_completed')
    safe_codes = ('selection_accessibility_required', 'selection_source_changed', 'selection_unavailable',
                  'selection_empty', 'selection_source_unresponsive', 'snippet_too_long', 'cancelled',
                  'capture_artifact_missing', 'selection_response_missing')
    reason = next((code for code in safe_codes if code in str(error)), 'other_failure' if error else None)
    return stage, reason


def render_error_suggestions(error: str) -> dict:
    """Trích xuất cờ gợi ý giao diện khi xảy ra lỗi."""
    err_str = str(error)
    cancelled = err_str.startswith('cancelled')
    return dict(
        cancelled=cancelled,
        # Same input fails the same way; a Retry button would only repeat it.
        retry_useful=not any(code in err_str for code in (
            'translation_local_pair_unavailable', 'invalid_snippet_length', 'snippet_chunk_limit', 'mini_llm_disabled'
        )),
        translation_suggested=any(code in err_str for code in (
            'translation_rate_limited', 'translation_quota_exhausted',
            'translation_api_key_missing', 'translation_auth_failed',
            'online_translation_not_enabled', 'api_key_missing'
        )),
        finder_suggested=any(code in err_str for code in (
            'no_search_roots', 'scope_revoked', 'spotlight_permission_denied'
        )),
        image_suggested=any(code in err_str for code in (
            'ocr_empty', 'image_input_invalid', 'source_expired', 'stale_source_ref', 'source_integrity_mismatch'
        )),
        status='Đã dừng tác vụ.' if cancelled else format_user_error_message(err_str)
    )


def format_user_error_message(error: str) -> str:
    """Ánh xạ mã lỗi thành thông báo tiếng Việt thân thiện."""
    messages = {
        'online_translation_not_enabled': 'MyMemory chưa được bật. Mở Cài đặt để chọn dịch trên máy hoặc cho phép MyMemory; đoạn chữ vẫn được giữ.',
        'spotlight_permission_denied': 'macOS chưa cho RAT đọc thư mục đã chọn. Kiểm tra quyền của RAT hoặc chọn thư mục khác.',
        'no_search_roots': 'Chọn ít nhất một thư mục trong Cài đặt để bắt đầu tìm file.',
        'scope_revoked': 'Danh sách thư mục đã thay đổi. Hãy tìm lại trước khi mở file.',
        'translation_local_unavailable': 'Gói dịch trong RAT chưa sẵn sàng. Hãy mở lại RAT; nếu vẫn lỗi, cài lại RAT từ file đã tải. Chữ vẫn được giữ.',
        'translation_local_pair_unavailable': 'RAT dịch Anh ↔ Việt. Đoạn này là ngôn ngữ khác nên chưa dịch được.',
        'translation_quota_exhausted': 'Dịch vụ đã hết hạn mức. Chữ vẫn được giữ; đổi dịch vụ hoặc chờ hạn mức khôi phục.',
        'translation_rate_limited': 'Dịch vụ đang giới hạn lượt dịch. Chữ vẫn được giữ; hãy thử lại sau ít phút.',
        'translation_auth_failed': 'Dịch vụ chưa chấp nhận cấu hình truy cập. Kiểm tra cài đặt dịch; chữ vẫn được giữ.',
        'translation_api_key_missing': 'Dịch vụ này chưa được cấu hình. Chọn dịch vụ khác trong Cài đặt; chữ vẫn được giữ.',
        'translation_timeout': 'Dịch vụ phản hồi quá lâu. Chữ vẫn được giữ; bạn có thể thử dịch lại.',
        'translation_tls_failed': 'Chưa kết nối an toàn được với dịch vụ dịch. Kiểm tra ngày giờ máy và mạng; chữ vẫn được giữ.',
        'translation_network_error': 'Chưa kết nối được dịch vụ dịch. Kiểm tra mạng rồi thử lại; chữ vẫn được giữ.',
        'translation_provider_error': 'Dịch vụ dịch chưa trả được kết quả. Chữ vẫn được giữ; hãy thử lại sau.',
        'mini_llm_disabled': 'Nhập từ khóa để tìm file, dán chữ để dịch Anh ↔ Việt trên máy, hoặc bật Suy luận Cloud (API key) trong Cài đặt để hỏi đáp/giải thích tự do.',
        'llm_disabled': 'Nhập từ khóa để tìm file, dán chữ để dịch Anh ↔ Việt trên máy, hoặc bật Suy luận Cloud (API key) trong Cài đặt để hỏi đáp/giải thích tự do.',
        'ambiguous_goal': 'Nhập từ khóa để tìm file, dán chữ để dịch Anh ↔ Việt trên máy, hoặc bật Suy luận Cloud (API key) trong Cài đặt để hỏi đáp/giải thích tự do.',
        'translation_failed': 'Chưa dịch được lúc này. Chữ vẫn được giữ; kiểm tra mạng rồi thử lại.'
    }
    for code, message in messages.items():
        if code in error:
            return message
    if any(code in error for code in ('stale_result_ref', 'result_expired', 'invalid_result_ref')):
        return 'Kết quả trước không còn hợp lệ. Hãy mở lại nguồn và thực hiện lại yêu cầu.'
    if any(code in error for code in ('source_integrity_mismatch', 'source_expired', 'stale_source_ref')):
        return 'Nguồn chữ cũ không còn hợp lệ. Hãy thả lại ảnh hoặc dán lại nội dung để dịch.'
    if 'selection_accessibility_required' in error:
        return 'Cho phép RAT trong Cài đặt hệ thống → Quyền riêng tư & Bảo mật → Trợ năng để đọc chữ bôi đen.'
    if 'selection_empty' in error:
        return 'Chưa thấy chữ được chọn. Bôi đen một đoạn rồi bấm lại.'
    if 'selection_source_unresponsive' in error:
        return 'App nguồn chưa phản hồi. Chờ một chút rồi thử lại, hoặc copy và chọn Dán chữ.'
    if 'selection_source_changed' in error:
        return 'App nguồn đã đổi. Hãy bôi đen chữ trong app cần đọc rồi bấm phím tắt dịch lại.'
    if 'selection_unavailable' in error:
        return 'Chưa lấy được chữ bôi đen từ app này. Bạn có thể dán chữ hoặc chọn vùng ảnh trong menu.'
    if 'selection_response_missing' in error:
        return 'Chưa nhận được chữ bôi đen. Hãy bôi đen chữ và thử lại nhé.'
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


def format_diagnostic_events(journal) -> list:
    """Chuẩn hóa 12 sự kiện gần nhất trong journal thành nhãn tiếng Việt."""
    labels = {
        'ready': 'Phím tắt đã đăng ký', 'selection': 'Đã nhận phím tắt',
        'invoked': 'Đã nhận yêu cầu', 'capture_requested': 'Đang lấy chữ',
        'capture_succeeded': 'Đã lấy được chữ', 'capture_failed': 'Chưa lấy được chữ',
        'translation_failed': 'Chưa xử lý được đoạn chữ', 'execution_completed': 'Đã xử lý',
        'present_requested': 'Đã yêu cầu hiển thị', 'presented': 'Đã hiển thị',
        'space_changed': 'Space đã đổi trong lúc gọi', 'space_policy_failed': 'Không đặt được cửa sổ trên Space hiện tại',
        'registration_failed': 'Đăng ký phím thất bại', 'ignored_busy': 'Đang bận', 'dismissed': 'Đã ẩn'
    }
    with journal.lock:
        return [dict(stage=e['stage'], label=labels.get(e['stage'], e['stage']), sequence=e['sequence'])
                for e in list(journal.events)[-12:]]
