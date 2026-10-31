"""Background worker and projection formatters for RAT Lite."""
from __future__ import annotations

import json
from pathlib import Path
from copy import deepcopy
from PyQt6.QtCore import QUrl
from rat.ui.mini_worker import MiniJob
from rat.ui.mini_diagnostics import BUILD
from rat.engine.mini_settings import save_settings, keychain_key
from rat.ui.image_input import IMAGE_SUFFIXES, ENCODED_IMAGE_TYPES, image_from_mime

REGION_PREVIOUS_FIELDS = (
    'phase', 'status', 'error', 'expanded', 'hasWorkbench', 'view',
    'agentSummary', 'agentIncomplete', 'settingsNotice', 'lastOperation',
    'translationSettingsSuggested', 'finderSettingsSuggested', 'imageInputSuggested',
    'organizationRecoverySuggested', 'canRetryRequest'
)

HISTORY_FIELDS = (
    'view', 'phase', 'status', 'error', 'text', 'meta', 'requestText',
    'hasWorkbench', 'pinned', 'attachmentLabel', 'finderHits', 'hasOcrSource', 'ocrText',
    'ocrCommittedText', 'ocrOriginalText', 'ocrPreparationNotice', 'captureSourceKind',
    'captureSourceApp', 'lookSource', 'translationDetails', 'translationNotice',
    'sameLanguageNotice', 'organization', 'organizationRows', 'organizationGroups',
    'agentSummary', 'agentIncomplete', 'lastOperation'
)


def default_controller_state(settings: dict) -> dict:
    """Khởi tạo toàn bộ từ điển trạng thái UI mặc định của RAT Lite."""
    return dict(
        draftText='', editingRequest=False, settingsNotice='', lastOperation='',
        organizationGroups=[], readinessSummary=[], agentSummary='', agentIncomplete=False,
        lookSource=False, hotkeyStatus='', sameLanguageNotice='', phase='idle', busy=False,
        bubbleCollapsed=False, expanded=False, selectionNotice='', selectionNeedsPermission=False,
        captureSourceApp='', captureSourceKind='', hotkeyStarting=False, shortcutAck='', pinned=False,
        hasWorkbench=False, view='idle', finderHits=[], text='', meta='', canReturnToFinder=False,
        status='Bạn muốn Chuột giúp gì?', requestText='', attachmentLabel='', error=False,
        ocrText='', ocrOriginalText='', ocrCommittedText='', hasOcrSource=False, canRetryTranslation=False,
        translationDetails='', translationNotice='', translationSettingsSuggested=False,
        dropActive=False, receivingImage=False, imagePreviewUrl='', imageLabel='',
        ocrPreparationNotice='', canRetryRequest=False, finderSettingsSuggested=False,
        imageInputSuggested=False, organization={}, organizationRows=[], canApplyOrganization=False,
        canUndoOrganization=False, organizationRecoverySuggested=False,
        setupCompleted=bool(settings.get("setup_completed", False) and settings.get('permission_hello_version', 0) >= 1),
        targetLanguage=settings.get('target_language', 'vi'),
        llmEnabled=bool(settings.get('llm_enabled', False)),
        readiness=[], readinessBusy=False, readinessStatus=""
    )


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
        translation_suggested=any(code in err_str for code in (
            'translation_rate_limited', 'translation_quota_exhausted',
            'translation_api_key_missing', 'translation_auth_failed',
            'translation_local_unavailable', 'online_translation_not_enabled', 'api_key_missing'
        )),
        finder_suggested=any(code in err_str for code in (
            'no_search_roots', 'scope_revoked', 'spotlight_permission_denied',
            'organization_folder_outside_scope', 'organization_scope_changed'
        )),
        image_suggested=any(code in err_str for code in (
            'ocr_empty', 'image_input_invalid', 'source_expired', 'stale_source_ref', 'source_integrity_mismatch'
        )),
        status='Đã dừng tác vụ.' if cancelled else format_user_error_message(err_str)
    )


def is_new_task_operation(operation: str, phase: str, args: dict) -> bool:
    """Xác định xem thao tác tiếp theo có bắt đầu một task hoàn toàn mới không."""
    return bool(
        operation in ('find_files', 'capture_translate', 'plan_folder_organization', 'get_last_organization')
        or (operation == 'submit_goal' and phase != 'needs_input' and not args.get('source_ref'))
        or (operation == 'translate_text' and not args.get('source_ref'))
    )


def get_frontmost_app_info() -> tuple[int | None, str, str | None]:
    """Lấy PID và localizedName của app nguồn phía trước trên macOS."""
    import sys
    import os
    if sys.platform != 'darwin':
        return None, '', 'unsupported_platform'
    try:
        from AppKit import NSWorkspace
        source = NSWorkspace.sharedWorkspace().frontmostApplication()
        if source is None or int(source.processIdentifier()) == os.getpid():
            return None, '', 'recall_own_app'
        return int(source.processIdentifier()), str(source.localizedName() or ''), None
    except Exception:
        return None, '', 'recall_own_app'


def pending_task_initial_updates(operation: str, args: dict, new_task: bool, preserve_region: bool,
                                 is_file_translate: bool, has_finder: bool, extent_expanded: bool) -> dict:
    """Tập hợp toàn bộ các trường update khi chuẩn bị chạy một job mới."""
    updates = {}
    if new_task and not preserve_region:
        updates.update(pinned=False, canApplyOrganization=False, canUndoOrganization=False, canReturnToFinder=False)
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
        if artifact.kind in ('organization_plan', 'organization_receipt'):
            is_plan = artifact.kind == 'organization_plan'
            view_org = format_organization_artifact_view(data, is_plan)
            return dict(
                kind='organization', artifact=artifact, data=data,
                update=dict(
                    view='organization', organization=data, organizationRows=view_org['rows'],
                    organizationGroups=view_org['groups'], organizationRecoverySuggested=False,
                    canApplyOrganization=view_org['can_apply'], canUndoOrganization=view_org['can_undo'],
                    phase='partial' if model_loop and is_agent_incomplete else 'result',
                    status=view_org['title'], text='',
                    meta=(data if is_plan else data.get('plan', {})).get('root', ''), finderHits=[]
                )
            )
        if artifact.kind == 'finder_results':
            hits = [dict(hit, kind='file', is_pdf=Path(hit['path']).suffix.lower() == '.pdf',
                         display_path=format_compact_display_path(hit['path']), match_reason='Spotlight') for hit in data['hits']]
            partial = data.get('status') == 'partial' or bool(data.get('provider_errors'))
            status = f"Tìm thấy {len(hits)} file" if hits else 'Chưa tìm thấy file trong thư mục đã chọn.'
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
                    view='translation', finderHits=[], text=data['text'], meta=view_data['meta'],
                    translationDetails=view_data['details'], translationNotice=view_data['notice'],
                    sameLanguageNotice=view_data['same_language_notice'], status=view_data['status'],
                    canReturnToFinder=view_data['can_return']
                )
            )
    return None




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


def format_translation_artifact_view(data: dict, finder_artifact_present: bool = False) -> dict:
    """Format meta, details, notice, same_language_notice, can_return, partial for translation view."""
    languages = {
        'vi': 'Tiếng Việt', 'en': 'Tiếng Anh', 'ja': 'Tiếng Nhật', 'ko': 'Tiếng Hàn',
        'zh': 'Tiếng Trung', 'fr': 'Tiếng Pháp', 'de': 'Tiếng Đức', 'es': 'Tiếng Tây Ban Nha',
        'auto': 'Tự nhận diện'
    }
    src_lang = data.get('source_language', '')
    tgt_lang = data.get('target_language', '')
    meta = f"{languages.get(src_lang, src_lang)} → {languages.get(tgt_lang, tgt_lang)}"
    if data.get('local_model'):
        meta = 'Dịch trên máy · ' + meta
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
        'details': details.strip(),
        'notice': notice,
        'same_language_notice': same_lang_msg,
        'can_return': can_return,
        'partial': partial,
        'status': 'Chưa dịch hết văn bản' if partial else 'Bản dịch',
    }


def format_organization_artifact_view(data: dict, is_plan: bool) -> dict:
    """Format organization plan or receipt into rows, groups and summary title."""
    plan = data if is_plan else data.get('plan', {})
    rows = (
        [dict(name=x['name'], destination=x['group']+'/'+x['name'], state='preview') for x in plan.get('moves', [])]
        if is_plan else
        [dict(name=x['name'], destination=x['group']+'/'+x['name'], state=x['state'], reason=x.get('reason', '')) for x in data.get('entries', [])]
    )
    moved = sum(x['state'] == 'moved' for x in rows)
    conflicts = sum(x['state'] in ('undo_conflict', 'identity_conflict') for x in rows)
    skipped_moves = sum(x['state'] in ('skipped', 'restored_conflict') for x in rows)
    counts = sum(plan.get('skipped', {}).values())
    title = f"Xem trước: {len(rows)} file · bỏ qua {counts}" if is_plan else f"Đã chuyển {moved} file · bỏ qua {skipped_moves} · {conflicts} xung đột"
    if data.get('status') == 'undone':
        title = 'Đã hoàn tác; các thư mục trống được giữ lại.'
    elif data.get('status') == 'empty':
        title = 'Chưa có lần sắp xếp nào.'
    grouped = {}
    for row in rows:
        group = row['destination'].split('/', 1)[0]
        grouped.setdefault(group, []).append(row)
    groups = [dict(name=name, count=len(items), rows=items) for name, items in grouped.items()]
    can_undo = not is_plan and any(x['state'] in ('moved', 'move_pending', 'undo_pending', 'undo_conflict') for x in rows)
    return {
        'rows': rows,
        'groups': groups,
        'title': title,
        'can_apply': is_plan and bool(rows),
        'can_undo': can_undo,
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


def record_finder_diagnostic(data: dict) -> None:
    """Ghi nhận receipt chẩn đoán ẩn danh của lần tìm kiếm gần nhất."""
    diagnostic = {
        'version': 'M5.16-source', 'status': data.get('status'),
        'coverage': data.get('coverage'), 'hit_count': data.get('hit_count'),
        'provider_errors': data.get('provider_errors'), 'diagnostics': data.get('diagnostics')
    }
    try:
        from rat.engine.mini_settings import state_directory
        folder = state_directory()
        folder.mkdir(parents=True, exist_ok=True)
        pending = folder / '.last-finder.json'
        pending.write_text(json.dumps(diagnostic, ensure_ascii=False), encoding='utf-8')
        pending.replace(folder / 'last-finder.json')
    except OSError:
        pass


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


def export_diagnostics_to_file(journal, url: str) -> str:
    """Xuất file chẩn đoán hệ thống an toàn không chứa nội dung nhạy cảm."""
    path = QUrl(url).toLocalFile()
    if not path:
        return 'Hãy chọn một file trên máy.'
    try:
        with journal.lock:
            payload = dict(build=BUILD, protocol='SELECT2',
                helper_state=journal.helper_state, events=list(journal.events))
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return ''
    except OSError:
        return 'Chưa ghi được file chẩn đoán ở vị trí này.'


def initial_operation_status(operation: str, args: dict) -> str:
    """Trạng thái ban đầu khi bắt đầu thực thi một tác vụ Mini."""
    capture_status = {
        'selection': 'Đang nhận chữ bôi đen…', 'region': 'Kéo chọn vùng chữ trên màn hình…',
        'image': 'Đang đọc chữ trong ảnh…', 'clipboard': 'Đang đọc Clipboard và dịch…',
        'file': 'Đang đọc file và dịch…'
    }.get(args.get('mode'), 'Đang nhận chữ…')
    return {
        'plan_folder_organization': 'Đang chuẩn bị bản xem trước…',
        'apply_folder_organization': 'Đang sắp xếp file…',
        'undo_folder_organization': 'Đang hoàn tác…',
        'get_last_organization': 'Đang đọc nhật ký…',
        'find_files': 'Đang tìm trong thư mục đã chọn…',
        'translate_text': 'Đang dịch…',
        'capture_translate': capture_status,
        'correct_translate': 'Đang ghi nhận chữ đã sửa và dịch lại…',
        'open_file': 'Đang mở file…',
        'reveal_file': 'Đang hiện trong Finder…'
    }.get(operation, 'Đang thực hiện…')


def validate_and_apply_preferences(settings: dict, changes: dict, secret: str = '',
                                   keychain_func=None, save_func=None) -> tuple[dict | None, str, bool]:
    """Kiểm tra và lưu các tùy chọn cài đặt mới."""
    try:
        updated = dict(settings)
        roots = changes.get('roots', updated.get('roots', []))
        roots = [str(Path(p).expanduser().resolve()) for p in roots if str(p).strip()]
        if any(not Path(p).is_dir() for p in roots):
            return None, 'Chọn thư mục đang tồn tại, hoặc bỏ thư mục không còn dùng.', False
        updated['roots'] = roots
        for name in ('source_language', 'target_language', 'translation_provider', 'free_fallback', 'provider', 'model', 'llm_enabled'):
            if name in changes:
                updated[name] = changes[name]
        if type(updated.get('llm_enabled', False)) is not bool:
            return None, 'Kiểm tra tùy chọn suy luận cloud.', False
        updated.setdefault('llm_enabled', False)
        if not updated['llm_enabled'] and updated.get('translation_provider') == 'llm':
            updated['translation_provider'] = 'automatic'
        if updated.get('provider') not in ('openai', 'deepseek', 'groq') or updated.get('translation_provider') not in ('automatic', 'google_gtx', 'mymemory', 'llm', 'deepl', 'google'):
            return None, 'Chọn một dịch vụ được hỗ trợ.', False
        for name, maximum in (('source_language', 35), ('target_language', 35), ('model', 128)):
            val = updated.get(name)
            if not isinstance(val, str) or not val.strip() or len(val) > maximum or '\0' in val:
                return None, 'Kiểm tra ngôn ngữ và tên model trong cài đặt.', False
            updated[name] = val.strip()
        if updated.get('target_language') == 'auto' or type(updated.get('free_fallback')) is not bool:
            return None, 'Chọn ngôn ngữ đích và tùy chọn dự phòng hợp lệ.', False
        if secret.strip():
            provider = (updated['translation_provider'] if updated['translation_provider'] in ('deepl', 'google')
                        else updated['provider'] if updated['llm_enabled'] else updated['translation_provider'])
            if provider not in ('openai', 'deepseek', 'groq', 'deepl', 'google'):
                return None, 'Dịch vụ miễn phí không dùng API key. Hãy bỏ key hoặc chọn dịch vụ có key.', False
            (keychain_func or keychain_key)(provider, secret)
        (save_func or save_settings)(updated)
        scopes_changed = updated['roots'] != settings.get('roots', [])
        return updated, '', scopes_changed
    except Exception as exc:
        return None, 'Chưa lưu được: ' + str(exc), False


def format_user_error_message(error: str) -> str:
    """Ánh xạ mã lỗi thành thông báo tiếng Việt thân thiện."""
    messages = {
        'online_translation_not_enabled': 'MyMemory chưa được bật. Mở Cài đặt để chọn dịch trên máy hoặc cho phép MyMemory; đoạn chữ vẫn được giữ.',
        'organization_folder_outside_scope': 'Thư mục này chưa thuộc phạm vi RAT. Thêm thư mục trong Cài đặt, rồi xem trước lại.',
        'organization_stale_preview': 'Bản xem trước đã quá 30 phút hoặc đã đổi. Hãy tạo bản xem trước mới.',
        'organization_scope_changed': 'Danh sách thư mục đã đổi. Hãy tạo bản xem trước mới.',
        'organization_folder_changed': 'Thư mục đã bị thay thế. Hãy chọn và xem trước lại.',
        'organization_explicit_approval_required': 'Chỉ áp dụng bằng nút trên bản xem trước hiện tại.',
        'spotlight_permission_denied': 'macOS chưa cho RAT đọc thư mục đã chọn. Kiểm tra quyền của RAT hoặc chọn thư mục khác.',
        'no_search_roots': 'Chọn ít nhất một thư mục trong Cài đặt để bắt đầu tìm file.',
        'scope_revoked': 'Danh sách thư mục đã thay đổi. Hãy tìm lại trước khi mở file.',
        'translation_local_unavailable': 'Gói dịch trên máy chưa sẵn sàng. Hãy mở lại app hoặc dùng lại bản ZIP đầy đủ; chữ vẫn được giữ.',
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


def parse_pasted_mime_content(mime, clipboard_text: str = '') -> dict:
    """Xử lý phân loại nội dung dán từ clipboard (file, ảnh hoặc chữ)."""
    if mime is None:
        return {'kind': 'typed', 'text': ''}
    local_urls = [u for u in mime.urls() if u.isLocalFile()] if mime.hasUrls() else []
    paths = [u.toLocalFile() for u in local_urls]
    if paths:
        if len(paths) == 1 and Path(paths[0]).suffix.lower() in IMAGE_SUFFIXES:
            try:
                image, name = image_from_mime(mime, clipboard=True)
                return {'kind': 'image', 'image': image, 'name': name}
            except ValueError as exc:
                return {'kind': 'error', 'error': str(exc)}
        return {'kind': 'file_reference', 'text': '\n'.join(paths)}
    if mime.hasImage() or any(mime.hasFormat(kind) for kind in ENCODED_IMAGE_TYPES):
        try:
            image, _ = image_from_mime(mime, clipboard=True)
            return {'kind': 'image', 'image': image, 'name': 'Ảnh vừa dán'}
        except ValueError as exc:
            return {'kind': 'error', 'error': str(exc)}
    return {'kind': 'pasted_text', 'text': clipboard_text}


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


from rat.os.hotkey_chords import DEFAULT_CHORD, chord
from rat.ui.mini_diagnostics import write_diagnostic
from rat.os.permissions import runtime_identity
from rat.mini import MiniSession


def format_finder_return_hits(artifact) -> list[dict]:
    raw_hits = artifact.payload.get('hits', []) if artifact else []
    return [dict(hit, kind='file', is_pdf=Path(hit['path']).suffix.lower() == '.pdf',
                 display_path=format_compact_display_path(hit['path']), match_reason='Spotlight')
            for hit in raw_hits]


def handle_file_action(artifact, index: int, operation: str, busy: bool) -> tuple[str, dict] | None:
    if busy or not artifact or not 0 <= index < len(artifact.payload.get('hits', [])):
        return None
    hit = artifact.payload['hits'][index]
    return operation, dict(artifact_id=artifact.id, revision=artifact.revision, resource_id=hit['resource_id'])


def change_shortcut_setting(settings: dict, name: str, rebind_hotkey) -> tuple[dict | None, str]:
    if not rebind_hotkey:
        return None, 'Chưa sẵn sàng đổi phím tắt.'
    try:
        chord(name)
        old = settings.get('hotkey_chord', DEFAULT_CHORD)
        error = rebind_hotkey(name)
        if error:
            return None, error
        try:
            updated = {**settings, 'hotkey_chord': name}
            save_settings(updated)
            return updated, ''
        except Exception:
            rollback_error = rebind_hotkey(old)
            return None, 'Chưa lưu được phím mới. ' + (rollback_error or 'Đã khôi phục phím cũ.')
    except ValueError:
        return None, 'Tổ hợp phím chưa được hỗ trợ.'


def write_ui_state_diagnostic(presentation, state: dict, generation: int) -> None:
    write_diagnostic('ui-state.json', dict(
        surface=presentation.surface, extent=presentation.extent,
        composer_visible=presentation.composer_visible, busy=state['busy'],
        phase=state['phase'], has_result=state['hasWorkbench'],
        operation=state['lastOperation'], task_id=presentation.task_id,
        generation=generation,
    ))


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


def save_preferences_settings(settings: dict, current_session, changes: dict, secret: str,
                            translation_args: dict | None, retry_request,
                            keychain_func=None, save_func=None) -> tuple[dict | None, any, str, bool, dict | None, any]:
    updated, err, scopes_changed = validate_and_apply_preferences(
        settings, changes, secret, keychain_func=keychain_func, save_func=save_func
    )
    if err:
        return None, None, err, False, translation_args, retry_request
    new_session = MiniSession(updated, artifact_store=current_session.runtime.artifact_store)
    new_session.pending_route, new_session.previous_goal = current_session.pending_route, current_session.previous_goal
    new_session.runtime.dispatcher.state.pending_input_request = current_session.runtime.dispatcher.state.pending_input_request
    new_tr_args = dict(translation_args) if translation_args else None
    if new_tr_args:
        for k in ('source_language', 'target_language'):
            if updated.get(k) != settings.get(k):
                new_tr_args[k] = updated[k]
    new_retry = retry_request
    if new_retry:
        op, args, q = new_retry
        args = dict(args)
        if op in ('capture_translate', 'translate_text'):
            for k in ('source_language', 'target_language'):
                args[k] = updated.get(k)
        new_retry = op, args, q
    return updated, new_session, '', scopes_changed, new_tr_args, new_retry

from rat.ui.image_input import image_from_url


def parse_image_url_input(url_or_urls, origin: str = 'dropped') -> tuple[any, str, str | None]:
    if origin == 'dropped':
        if len(url_or_urls) != 1:
            return None, '', 'Hãy thả từng ảnh một để RAT dịch.'
        target = url_or_urls[0]
    else:
        target = url_or_urls
    try:
        image, name = image_from_url(target, origin='selected_file' if origin != 'dropped' else 'dropped')
        return image, name, None
    except ValueError as exc:
        return None, '', str(exc)
