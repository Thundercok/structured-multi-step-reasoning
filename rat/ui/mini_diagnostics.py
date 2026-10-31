"""QA and support metadata. Never records input text or runs business tools."""
import json
import logging
import os
from pathlib import Path

from PyQt6.QtCore import QUrl

from rat.engine.mini_settings import state_directory
from rat.engine.mini_version import BUILD
logger = logging.getLogger(__name__)


def write_diagnostic(name, values):
    root = os.environ.get('RAT_MINI_ACCEPTANCE_DIR')
    if not root:
        return True
    try:
        folder = Path(root)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        temporary = folder / (name + '.tmp')
        temporary.write_text(json.dumps(dict(build=BUILD, pid=os.getpid(), **values), ensure_ascii=False, indent=2))
        temporary.replace(target)
        return True
    except Exception as exc:
        # Avoid an exception repr that could contain user data from a serializer.
        logger.warning('qa_metadata_write_failed name=%s type=%s', name, type(exc).__name__)
        return False


def record_finder_diagnostic(data: dict) -> None:
    """Ghi nhận receipt chẩn đoán ẩn danh của lần tìm kiếm gần nhất."""
    diagnostic = {
        'version': 'M5.16-source', 'status': data.get('status'),
        'coverage': data.get('coverage'), 'hit_count': data.get('hit_count'),
        'provider_errors': data.get('provider_errors'), 'diagnostics': data.get('diagnostics')
    }
    try:
        folder = state_directory()
        folder.mkdir(parents=True, exist_ok=True)
        pending = folder / '.last-finder.json'
        pending.write_text(json.dumps(diagnostic, ensure_ascii=False), encoding='utf-8')
        pending.replace(folder / 'last-finder.json')
    except OSError:
        pass


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


def write_ui_state_diagnostic(presentation, state: dict, generation: int) -> None:
    write_diagnostic('ui-state.json', dict(
        surface=presentation.surface, extent=presentation.extent,
        composer_visible=presentation.composer_visible, busy=state['busy'],
        phase=state['phase'], has_result=state['hasWorkbench'],
        operation=state['lastOperation'], task_id=presentation.task_id,
        generation=generation,
    ))
