"""Find installed macOS apps by what they do, not only by their name.

"app chỉnh ảnh" should reach Photoshop or Preview even when the user has
forgotten the name. Each catalogued app gets a short description from its own
Info.plist category plus a curated Vietnamese phrase for common apps; the
descriptions share the file index's on-device embedder. Nothing is launched
here: opening goes through the applications capability, which revalidates the
bundle first.
"""
from __future__ import annotations

from pathlib import Path
import plistlib
import threading

import numpy as np

from rat.engine.app_resolver import ApplicationCatalog, name_key

CATEGORY_TEXT = {
    'productivity': 'năng suất, công việc văn phòng', 'business': 'công việc, kinh doanh',
    'education': 'học tập, giáo dục', 'reference': 'tra cứu, từ điển', 'utilities': 'tiện ích hệ thống',
    'developer-tools': 'lập trình, viết code', 'graphics-design': 'thiết kế đồ họa, vẽ, chỉnh ảnh',
    'photography': 'ảnh, chỉnh sửa ảnh', 'video': 'video, dựng phim, xem phim', 'music': 'nhạc, nghe nhạc',
    'social-networking': 'mạng xã hội, nhắn tin, chat', 'entertainment': 'giải trí',
    'games': 'trò chơi, game', 'finance': 'tài chính, tiền', 'news': 'tin tức, đọc báo',
    'weather': 'thời tiết', 'travel': 'du lịch, bản đồ', 'lifestyle': 'đời sống',
    'healthcare-fitness': 'sức khỏe, tập luyện', 'medical': 'y tế',
}

# Purposes for apps students commonly have; matched by bundle id, never by guessed paths.
KNOWN_APPS = {
    'com.apple.notes': 'ghi chú, viết nhanh ý tưởng',
    'com.apple.reminders': 'nhắc việc, danh sách việc cần làm',
    'com.apple.ical': 'lịch, lịch học, lịch hẹn',
    'com.apple.mail': 'email, thư điện tử',
    'com.apple.safari': 'trình duyệt web, lướt web',
    'com.google.chrome': 'trình duyệt web, lướt web',
    'com.apple.preview': 'xem pdf, xem ảnh, ký tài liệu',
    'com.apple.calculator': 'máy tính, tính toán',
    'com.apple.textedit': 'soạn thảo văn bản đơn giản',
    'com.apple.iwork.pages': 'soạn thảo văn bản, viết báo cáo',
    'com.apple.iwork.keynote': 'làm slide, thuyết trình',
    'com.apple.iwork.numbers': 'bảng tính',
    'com.microsoft.word': 'soạn thảo văn bản, viết báo cáo, word',
    'com.microsoft.excel': 'bảng tính, excel, tính điểm',
    'com.microsoft.powerpoint': 'làm slide, thuyết trình, powerpoint',
    'com.microsoft.teams2': 'họp trực tuyến, học online',
    'com.microsoft.teams': 'họp trực tuyến, học online',
    'us.zoom.xos': 'họp trực tuyến, học online, gọi video',
    'com.vng.zalo': 'nhắn tin, chat, gọi điện',
    'com.facebook.archon': 'nhắn tin messenger, chat',
    'com.tinyspeck.slackmacgap': 'nhắn tin nhóm, chat công việc',
    'com.hnc.discord': 'nhắn tin, chat, gọi thoại nhóm',
    'ru.keepcoder.telegram': 'nhắn tin, chat',
    'com.apple.mobilesms': 'nhắn tin, tin nhắn',
    'com.apple.facetime': 'gọi video',
    'com.spotify.client': 'nghe nhạc',
    'com.apple.music': 'nghe nhạc',
    'com.apple.photos': 'xem ảnh, thư viện ảnh',
    'com.adobe.photoshop': 'chỉnh sửa ảnh, thiết kế',
    'com.figma.desktop': 'thiết kế giao diện, vẽ',
    'com.microsoft.vscode': 'viết code, lập trình',
    'com.apple.dt.xcode': 'lập trình ứng dụng apple',
    'com.apple.terminal': 'dòng lệnh, terminal',
    'com.apple.finder': 'quản lý file, thư mục',
    'com.apple.systempreferences': 'cài đặt máy, cài đặt hệ thống',
    'com.apple.appstore': 'tải ứng dụng',
    'com.apple.screenshot.launcher': 'chụp màn hình, quay màn hình',
    'com.apple.quicktimeplayerx': 'xem video, quay màn hình',
    'com.apple.dictionary': 'từ điển, tra từ',
    'notion.id': 'ghi chú, quản lý công việc',
    'com.openai.chat': 'trợ lý ai, chatgpt',
    'com.anthropic.claudefordesktop': 'trợ lý ai, claude',
    'com.capcut.capcut': 'dựng video, chỉnh video',
    'com.apple.finalcutapp': 'dựng phim, chỉnh video',
    'com.google.drivefs': 'lưu trữ đám mây, google drive',
}


GENERIC_WORDS = {'app', 'apps', 'ung', 'dung', 'phan', 'mem', 'tim', 'mo', 'de', 'giup', 'minh', 'toi'}


def app_descriptions(app):
    """Purpose and category phrases, embedded separately so neither dilutes the other."""
    texts = []
    purpose = KNOWN_APPS.get(app.bundle_id.casefold())
    if purpose:
        texts.append(purpose)
    try:
        with open(Path(app.path) / 'Contents/Info.plist', 'rb') as handle:
            raw = plistlib.load(handle).get('LSApplicationCategoryType', '')
        category = CATEGORY_TEXT.get(str(raw).rsplit('.', 1)[-1])
        if category:
            texts.append(category)
    except Exception:
        pass
    return texts


class AppSearch:
    """Catalog scanned once per process; descriptions embedded on first use."""

    def __init__(self, embedder_source, catalog_cache=None):
        self._embedder_source = embedder_source
        self._catalog_cache = catalog_cache
        self._lock = threading.Lock()
        self._apps = None
        self._matrix = None

    def _load(self):
        with self._lock:
            if self._apps is None:
                catalog = ApplicationCatalog.scan(cache_path=self._catalog_cache) if self._catalog_cache else ApplicationCatalog.scan()
                self._apps = [a for a in catalog.applications if not a.path.startswith('/System/Library/')]
                self._names = [[name_key(n) for n in a.names] for a in self._apps]
            if self._matrix is None and self._apps:
                owners, texts = [], []
                for i, app in enumerate(self._apps):
                    for text in app_descriptions(app):
                        owners.append(i); texts.append(text)
                self._owners = np.array(owners, dtype=int)
                self._words = [set(name_key(' '.join(app_descriptions(a))).split()) for a in self._apps]
                # Apps with only a bare name compete by name, never on meaning.
                self._matrix = (self._embedder_source().embed_texts(texts, batch_size=16)
                                if texts else np.empty((0, 384), dtype=np.float32))
            return self._apps, self._matrix

    def search(self, query, limit=3, floor=0.5):
        apps, matrix = self._load()
        if not apps:
            return []
        # "app"/"ứng dụng" says what kind of thing, not which one; left in, it
        # pulls "Apps" and "App Store" to the top. Accents stay for the model:
        # folded Vietnamese loses its meaning.
        text = ' '.join(w for w in query.split() if name_key(w) not in GENERIC_WORDS)
        key = name_key(text)
        if not key:
            return []
        meaning = np.zeros(len(apps), dtype=np.float32)
        if len(matrix):
            np.maximum.at(meaning, self._owners, matrix @ self._embedder_source().embed_query(text))
        terms = set(key.split())
        agreement = np.array([len(terms & words) / len(terms) for words in self._words], dtype=np.float32)
        named = np.array([any(n == key or n.startswith(key) or key in n.split() for n in names)
                          for names in self._names])
        scores = meaning + 0.3 * agreement + 0.6 * named
        results = []
        for i in np.argsort(-scores)[:limit]:
            if scores[i] < floor:
                break
            app = apps[i]
            results.append({'kind': 'app', 'title': app.name, 'path': app.path, 'bundle_id': app.bundle_id,
                            'resource_id': app.resource_id, 'score': round(float(scores[i]), 3),
                            'named': bool(named[i])})
        return results
