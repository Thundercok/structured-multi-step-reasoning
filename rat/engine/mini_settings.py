"""Portable mini product configuration; secrets live in macOS Keychain, never JSON."""
from __future__ import annotations

from rat.os.hotkey_chords import CHORDS, DEFAULT_CHORD

import ctypes
import ctypes.util
import json
import os
from pathlib import Path
import tempfile


def state_directory():
    return Path(os.environ.get('RAT_MINI_STATE_DIR') or
                Path.home() / 'Library/Application Support/RAT Mini').expanduser()


DEFAULTS = {'roots': [str(Path.home()/name) for name in ('Documents','Desktop','Downloads')], 'provider': 'openai', 'model': 'gpt-4.1-mini',
            'translation_provider': 'automatic', 'free_fallback': True, 'llm_enabled': False,
            'hotkey_chord': DEFAULT_CHORD, 'target_language': 'vi', 'source_language': 'auto', 'semantic_enabled': False, 'setup_completed': False}


def read_settings():
    try:
        data = json.loads((state_directory() / 'settings.json').read_text())
        if not isinstance(data, dict):
            return {**DEFAULTS, 'roots': list(DEFAULTS['roots'])}
        result = {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}
        roots = result['roots']
        if not isinstance(roots, list) or not 0 < len(roots) <= 32 or not all(
                isinstance(root, str) and root.strip() and '\0' not in root for root in roots):
            result['roots'] = list(DEFAULTS['roots'])
        else:
            result['roots'] = list(dict.fromkeys(str(Path(root).expanduser()) for root in roots))
        if result['translation_provider'] == 'apple':
            result['translation_provider'] = 'google_gtx'
        if result['translation_provider'] not in ('automatic','google_gtx','mymemory','deepl','google','llm'):
            result['translation_provider'] = DEFAULTS['translation_provider']
        if result['provider'] not in ('openai','deepseek','groq'):
            result['provider'] = DEFAULTS['provider']
        for key in ('source_language','target_language','model'):
            limit = 128 if key == 'model' else 35
            if not isinstance(result[key], str) or not result[key].strip() or len(result[key]) > limit:
                result[key] = DEFAULTS[key]
            else:
                result[key] = result[key].strip()
        if result['target_language'] == 'auto':
            result['target_language'] = DEFAULTS['target_language']
        if type(result['free_fallback']) is not bool:
            result['free_fallback'] = DEFAULTS['free_fallback']
        result['llm_enabled'] = result.get('llm_enabled') is True
        if not result['llm_enabled'] and result['translation_provider'] == 'llm':
            result['translation_provider'] = 'automatic'
        if type(result['setup_completed']) is not bool:
            result['setup_completed'] = False
        if result['hotkey_chord'] not in CHORDS:
            result['hotkey_chord'] = DEFAULT_CHORD
        result['semantic_enabled'] = False
        return result
    except (OSError, ValueError, TypeError):
        return {**DEFAULTS, 'roots':list(DEFAULTS['roots'])}


def save_settings(data):
    root = state_directory()
    root.mkdir(parents=True, exist_ok=True)
    safe = {k: data.get(k, v) for k, v in DEFAULTS.items()}
    fd, filename = tempfile.mkstemp(dir=root, prefix='.settings-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(safe, stream, ensure_ascii=False, indent=2)
        os.replace(filename, root / 'settings.json')
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def keychain_key(provider, value=None):
    """Find/add/update one generic password via Security; no key in subprocess args."""
    if provider not in {'openai', 'deepseek', 'groq', 'deepl', 'google'}:
        raise ValueError('unknown_provider')
    sec = ctypes.CDLL(ctypes.util.find_library('Security'))
    u32, ptr = ctypes.c_uint32, ctypes.c_void_p
    service, account = b'vn.rat.mini.api', provider.encode()
    sec.SecKeychainFindGenericPassword.argtypes = [ptr, u32, ctypes.c_char_p, u32, ctypes.c_char_p,
                                                  ctypes.POINTER(u32), ctypes.POINTER(ptr), ctypes.POINTER(ptr)]
    sec.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    sec.SecKeychainItemFreeContent.argtypes = [ptr, ptr]
    sec.SecKeychainItemModifyAttributesAndData.argtypes = [ptr, ptr, u32, ptr]
    sec.SecKeychainAddGenericPassword.argtypes = [ptr, u32, ctypes.c_char_p, u32, ctypes.c_char_p, u32, ptr, ptr]
    sec.CFRelease = ctypes.CDLL(ctypes.util.find_library('CoreFoundation')).CFRelease
    sec.CFRelease.argtypes = [ptr]
    length, content, item = u32(), ptr(), ptr()
    status = sec.SecKeychainFindGenericPassword(None, len(service), service, len(account), account,
                                               ctypes.byref(length), ctypes.byref(content), ctypes.byref(item))
    try:
        if value is None:
            if status == -25300:
                return os.environ.get({'openai':'OPENAI_API_KEY','deepseek':'DEEPSEEK_API_KEY',
                                       'groq':'GROQ_API_KEY','deepl':'DEEPL_API_KEY','google':'GOOGLE_API_KEY'}[provider], '')
            if status:
                raise ValueError(f'keychain_error:{status}')
            return ctypes.string_at(content, length.value).decode()
        secret = value.strip().encode()
        if not secret:
            raise ValueError('empty_api_key')
        if status == 0:
            result = sec.SecKeychainItemModifyAttributesAndData(item, None, len(secret), secret)
        elif status == -25300:
            result = sec.SecKeychainAddGenericPassword(None, len(service), service, len(account), account,
                                                      len(secret), secret, None)
        else:
            raise ValueError(f'keychain_error:{status}')
        if result:
            raise ValueError(f'keychain_error:{result}')
        return True
    finally:
        if content:
            sec.SecKeychainItemFreeContent(None, content)
        if item:
            sec.CFRelease(item)
