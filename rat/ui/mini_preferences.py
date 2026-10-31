"""RAT Lite settings and shortcut changes: validate, persist, rebuild the session."""
from __future__ import annotations

from pathlib import Path

from rat.engine.mini_settings import save_settings, keychain_key
from rat.mini import MiniSession
from rat.os.hotkey_chords import DEFAULT_CHORD, chord


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
