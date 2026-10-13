"""Public execution summaries, never raw model reasoning or verification claims."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TraceEntry:
    number: int
    title: str
    detail: str = ''
    status: str = 'done'


LABELS = {
    'search_documents': 'Tìm tài liệu', 'read_document': 'Đọc tài liệu',
    'get_schedule': 'Xem lịch học', 'get_group_availability': 'Đối chiếu lịch rảnh',
    'calculate': 'Tính toán', 'locate_room': 'Tra vị trí phòng',
    'create_natal_chart': 'Tính lá số', 'update_birth_data': 'Cập nhật lá số',
    'export_natal_chart': 'Xuất lá số', 'search_birth_places': 'Tra nơi sinh',
    'inspect_artifact': 'Đọc lại kết quả', 'record_work_note': 'Ghi chép dữ kiện',
    'update_task_state': 'Sắp xếp công việc',
    'select_work_results': 'Chọn kết quả cho công việc',
}


def summarize_step(step):
    """Only observed calls/results and explicitly labeled structured plans."""
    result = step.tool_result
    result = result if isinstance(result, dict) else {'items': result} if isinstance(result, list) else {}
    name = step.tool_name
    checks = getattr(step, 'verification', [])
    if checks and not name:
        status = 'error' if any(c['status'] == 'FAIL' for c in checks) else 'unchecked' if any(c['status'] == 'UNKNOWN' for c in checks) else 'done'
        return TraceEntry(step.step_number, 'Đối chiếu kết luận', '\n'.join(c['reason'] for c in checks), status)
    if step.error:
        return TraceEntry(step.step_number, 'Chưa thực hiện được bước này', str(step.error)[:300], 'error')
    if result.get('error') == 'duplicate_action':
        return TraceEntry(step.step_number, 'Dừng thao tác lặp lại', 'Dùng các kết quả đã có để trả lời.', 'stopped')
    if result.get('controller'):
        return TraceEntry(step.step_number, 'Dừng gọi thêm công cụ', 'Bộ điều phối yêu cầu tổng hợp từ dữ kiện đã có.', 'stopped')
    if name == 'update_task_state':
        state = result.get('task_state', {})
        parts = [state.get('goal', ''), *state.get('remaining', [])[:3]]
        return TraceEntry(step.step_number, 'Dự định làm việc', '\n'.join(p for p in parts if p), 'proposed')
    if not name:
        return TraceEntry(step.step_number, 'Đưa câu trả lời', 'Câu trả lời đã được model trả về.')
    detail = ''
    status = 'done'
    if result.get('error') or result.get('found') is False:
        detail, status = str(result.get('error') or 'Chưa có dữ liệu phù hợp.')[:300], 'error'
    elif result.get('status') == 'needs_input':
        detail, status = result.get('prompt', 'Cần thêm dữ kiện để tiếp tục.'), 'waiting'
    elif name == 'record_work_note':
        note = result.get('note', {})
        detail = note.get('text', '')
        if not note.get('confirmed'):
            status = 'proposed'
    elif name == 'read_document':
        detail = result.get('filename') or Path(result.get('path', '')).name
        if result.get('truncated'):
            detail += ' · đã đọc phần đầu'
    elif 'items' in result and isinstance(result['items'], list):
        detail = f"Có {len(result['items'])} kết quả từ công cụ."
    elif name == 'calculate':
        detail = f"{result.get('expression', '')} = {result.get('result', '')}"
        if checks:
            detail += '\n' + '\n'.join(c['reason'] for c in checks)
            if any(c['status'] == 'FAIL' for c in checks):
                status = 'error'
            elif any(c['status'] == 'UNKNOWN' for c in checks):
                status = 'unchecked'
    elif 'result_refs' in result:
        detail = f"Giữ {len(result['result_refs'])} kết quả để tiếp tục làm việc."
    for artifact in getattr(step, 'artifacts', []):
        if artifact.status == 'waiting_input':
            status = 'waiting'
            detail = artifact.payload.get('prompt', detail)
    return TraceEntry(step.step_number, LABELS.get(name, 'Thực hiện thao tác'), detail, status)
