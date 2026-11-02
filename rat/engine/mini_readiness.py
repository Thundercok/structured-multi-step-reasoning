"""Local setup observations. No permission requests, clipboard, network or inference."""
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys
import time
from rat.engine.local_translation import LocalTranslator, is_local_models_ready, ensure_local_translation_models


def check_readiness(settings, *, deep=False, cancel=lambda: False):
    checks = []
    def add(key, label, state, detail):
        checks.append(dict(key=key, label=label, state=state, detail=detail))
    supported = sys.platform == 'darwin' and platform.machine() == 'arm64'
    version = platform.mac_ver()[0]
    supported = supported and bool(version) and int(version.split('.')[0]) >= 14
    add('platform', 'Máy Mac', 'ready' if supported else 'action_required',
        'Hỗ trợ Apple Silicon, macOS 14 trở lên.' if supported else 'Bản này dành cho Apple Silicon, macOS 14 trở lên.')
    add('spotlight', 'Tìm file', 'ready' if shutil.which('mdfind') else 'action_required',
        'Spotlight có sẵn. Kết quả còn phụ thuộc thư mục đã được macOS lập chỉ mục.')
    for module, label in [('Vision','Đọc chữ trong ảnh'), ('ctranslate2','Bộ dịch trên máy'), ('sentencepiece','Bộ đọc văn bản')]:
        if module == 'Vision':
            try:
                from rat.crawler.apple_vision import _init_apple_vision
                found = _init_apple_vision()
            except Exception:
                found = False
        else:
            found = importlib.util.find_spec(module) is not None
        add(module, label, 'ready' if found else 'action_required',
            'Sẵn sàng hoạt động trên máy.' if found else 'Thiếu thành phần. Hãy tải lại bản app đầy đủ.')
    folder = LocalTranslator().directory
    if not is_local_models_ready(folder):
        try:
            ensure_local_translation_models(folder, cancel=cancel)
        except Exception:
            pass
    try:
        manifest = json.loads((folder/'manifest.json').read_text())
        for pair in ('en-vi','vi-en'):
            okay = True
            for name, expected in manifest['models'][pair]['files'].items():
                if cancel():
                    raise ValueError('cancelled:readiness')
                path = folder/pair/name
                if not path.is_file():
                    okay = False
                    break
                if deep:
                    hasher = hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(1024*1024), b''):
                            if cancel():
                                raise ValueError('cancelled:readiness')
                            hasher.update(chunk)
                    okay = okay and hasher.hexdigest() == expected
            add(pair, 'Gói dịch ' + ('Anh → Việt' if pair == 'en-vi' else 'Việt → Anh'), 'ready' if okay else 'action_required',
                'Đã đối chiếu tính toàn vẹn gói dịch.' if okay and deep else 'Sẵn sàng dịch ngoại tuyến tức thì.' if okay else 'Gói dịch thiếu hoặc không khớp. Hãy dùng lại ZIP đầy đủ.')
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        add('models', 'Gói dịch', 'action_required', 'Chưa đọc được gói dịch. Hãy dùng lại ZIP đầy đủ.')
    roots = settings.get('roots', [])
    present = sum(Path(p).expanduser().is_dir() for p in roots)
    add('folders', 'Thư mục tìm kiếm', 'ready' if present > 0 else 'action_required',
        f'Đã kết nối {present}/{len(roots)} thư mục.' if present > 0 else 'Chưa kết nối được thư mục nào; có thể thêm trong Cài đặt.')
    if sys.platform == 'darwin':
        from rat.os.permissions import accessibility_status
        ax = accessibility_status()
        add('accessibility', 'Đọc chữ bôi đen', 'ready' if ax.trusted else 'action_required',
            'Đã cấp quyền đọc chữ bôi đen.' if ax.trusted else
            'Cần bật Trợ năng để đọc chữ bôi đen bằng phím tắt. Nhấn Mở Trợ năng để cấp quyền.')
        try:
            import Quartz
            screen_granted = bool(Quartz.CGPreflightScreenCaptureAccess())
            add('screen', 'Chọn vùng trên màn hình', 'ready' if screen_granted else 'not_required',
                'Đã cấp Ghi màn hình.' if screen_granted else
                'Chỉ cần Ghi màn hình khi bạn dùng Chọn vùng chữ; ảnh thả vào và chữ dán không cần quyền này.')
        except Exception:
            add('screen', 'Chọn vùng trên màn hình', 'unverified', 'Chưa kiểm tra được quyền Ghi màn hình.')
    else:
        add('accessibility', 'Đọc chữ bôi đen', 'not_required', 'Chức năng selection chỉ hỗ trợ macOS.')
        add('screen', 'Chọn vùng trên màn hình', 'not_required', 'Chức năng chọn vùng chỉ hỗ trợ macOS.')
    add('network', 'Dịch trực tuyến', 'not_required',
        'Anh ↔ Việt dịch ngay trên máy. Ngôn ngữ khác cần mạng và dịch vụ tương ứng; chưa kiểm chứng kết nối.')
    return dict(status='needs_attention' if any(c['state']=='action_required' for c in checks) else 'ready',
        checks=checks, checked_at=time.time(), deep=deep)
