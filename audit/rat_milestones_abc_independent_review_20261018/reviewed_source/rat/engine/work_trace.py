"""Public execution summaries, never raw model reasoning or verification claims."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence


@dataclass
class TraceEntry:
    number: int
    title: str
    detail: str = ''
    status: str = 'done'
    stage: str = ''
    evidence_ref: str = ''
    receipt_id: str = ''
    resource_id: str = ''
    artifact_id: str = ''
    revision: Optional[int] = None


LABELS = {
    'search_documents': 'Tìm tài liệu',
    'read_document': 'Đọc tài liệu',
    'search_book_pages': 'Tìm trang sách',
    'read_book_page': 'Đọc trang sách',
    'deliver_document': 'Giao tệp gốc',
    'read_web_page': 'Đọc trang web',
    'open_application': 'Mở ứng dụng',
    'get_schedule': 'Xem lịch học',
    'get_group_availability': 'Đối chiếu lịch rảnh',
    'calculate': 'Tính toán',
    'locate_room': 'Tra vị trí phòng',
    'create_natal_chart': 'Tính lá số',
    'update_birth_data': 'Cập nhật lá số',
    'export_natal_chart': 'Xuất lá số',
    'search_birth_places': 'Tra nơi sinh',
    'inspect_artifact': 'Đọc lại kết quả',
    'record_work_note': 'Ghi chép dữ kiện',
    'update_task_state': 'Sắp xếp công việc',
    'select_work_results': 'Chọn kết quả cho công việc',
    'request_operation_tools': 'Mở công cụ thao tác',
    'dismiss_pending_input': 'Đóng yêu cầu nhập cũ',
}


def _stage_for_tool(name: Optional[str]) -> str:
    if name in ('search_documents', 'search_book_pages', 'search_birth_places'):
        return 'search'
    if name in ('read_document', 'read_book_page', 'read_web_page', 'inspect_artifact', 'get_schedule', 'get_group_availability', 'locate_room'):
        return 'read'
    if name in ('calculate',):
        return 'verify'
    if name in ('update_task_state', 'select_work_results', 'request_operation_tools'):
        return 'plan'
    return 'result'


def summarize_step(step):
    """Only observed calls/results and explicitly labeled structured plans."""
    result = step.tool_result
    result = result if isinstance(result, dict) else {'items': result} if isinstance(result, list) else {}
    name = step.tool_name
    checks = getattr(step, 'verification', [])
    artifacts = getattr(step, 'artifacts', []) or []
    first_art = artifacts[0] if artifacts else None
    art_id = getattr(first_art, 'id', '') if first_art is not None else ''
    art_rev = getattr(first_art, 'revision', None) if first_art is not None else None
    ev_ref = f"{art_id}@v{art_rev}" if art_id and art_rev is not None else art_id

    if checks and not name:
        status = 'error' if any(c['status'] == 'FAIL' for c in checks) else 'unchecked' if any(c['status'] == 'UNKNOWN' for c in checks) else 'done'
        return TraceEntry(
            step.step_number,
            'Đối chiếu kết luận',
            '\n'.join(c['reason'] for c in checks),
            status,
            stage='verify',
            evidence_ref=ev_ref,
        )
    if step.error:
        return TraceEntry(
            step.step_number,
            'Chưa thực hiện được bước này',
            str(step.error)[:300],
            'error',
            stage=_stage_for_tool(name),
            evidence_ref=ev_ref,
        )
    if result.get('error') == 'duplicate_action':
        return TraceEntry(
            step.step_number,
            'Dừng thao tác lặp lại',
            'Dùng các kết quả đã có để trả lời.',
            'stopped',
            stage='verify',
        )
    if result.get('controller'):
        return TraceEntry(
            step.step_number,
            'Dừng gọi thêm công cụ',
            'Bộ điều phối yêu cầu tổng hợp từ dữ kiện đã có.',
            'stopped',
            stage='verify',
        )
    if result.get('phase') == 'initial_plan' and not name:
        contract = result.get('contract') or {}
        outcomes = contract.get('outcomes', []) if isinstance(contract, dict) else []
        desc_parts = [
            str(o.get('description') or o.get('effect_type') or o.get('kind') or '')
            for o in outcomes[:4]
            if isinstance(o, dict)
        ]
        detail = ' → '.join(p for p in desc_parts if p) or 'Đã lập kế hoạch các bước cần thực hiện.'
        return TraceEntry(step.step_number, 'Dự định làm việc', detail, 'proposed', stage='plan')
    if result.get('completion_feedback') and not name:
        fb = result['completion_feedback']
        unmet = fb.get('unmet_outcomes', []) if isinstance(fb, dict) else []
        reasons = [str(u.get('description') or u.get('outcome_id') or '') for u in unmet[:3] if isinstance(u, dict)]
        detail = 'Còn thiếu: ' + ', '.join(r for r in reasons if r) if reasons else 'Còn phần việc đã khai chưa thực hiện.'
        return TraceEntry(step.step_number, 'Kiểm tra điều kiện hoàn tất', detail, 'unchecked', stage='verify')
    if name == 'update_task_state':
        state = result.get('task_state', {})
        parts = [state.get('goal', ''), *state.get('remaining', [])[:3]]
        return TraceEntry(step.step_number, 'Dự định làm việc', '\n'.join(p for p in parts if p), 'proposed', stage='plan')
    if not name:
        return TraceEntry(step.step_number, 'Đưa câu trả lời', 'Câu trả lời đã được model trả về.', 'done', stage='result')

    detail = ''
    status = 'done'
    stage = _stage_for_tool(name)
    res_id = str(result.get('resource_id') or result.get('path') or '')

    if result.get('error') or result.get('found') is False:
        detail, status = str(result.get('error') or 'Chưa có dữ liệu phù hợp.')[:300], 'error'
    elif result.get('status') == 'needs_input':
        detail, status, stage = result.get('prompt', 'Cần thêm dữ kiện để tiếp tục.'), 'waiting', 'clarify'
    elif name == 'record_work_note':
        note = result.get('note', {})
        detail = note.get('text', '')
        if not note.get('confirmed'):
            status = 'proposed'
    elif name == 'read_document':
        detail = result.get('filename') or Path(result.get('path', '')).name
        content = result.get('content', '')
        total_chars = result.get('total_chars')
        if isinstance(content, str) and content and total_chars:
            detail += f" ({len(content):,}/{int(total_chars):,} ký tự)"
        if result.get('truncated'):
            detail += ' · đã đọc phần đầu'
    elif name == 'read_book_page':
        fn = result.get('filename') or Path(result.get('path', '')).name
        pg = result.get('page', 1)
        lbl = result.get('page_label', pg)
        detail = f"{fn} · trang PDF {pg} (nhãn {lbl})"
        if result.get('truncated'):
            detail += ' · đã đọc phần đầu'
    elif name == 'search_book_pages':
        fn = result.get('filename') or Path(result.get('path', '')).name
        matched = result.get('matched_pages', 0)
        detail = f"{fn} · {matched} trang khớp"
    elif name == 'open_application':
        app_name = result.get('name') or 'Ứng dụng'
        detail = f"{app_name} · Đã gửi lệnh mở tới macOS (chưa xác nhận vào trong ứng dụng)"
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
    for artifact in artifacts:
        if artifact.status == 'waiting_input':
            status = 'waiting'
            stage = 'clarify'
            detail = artifact.payload.get('prompt', detail)
    return TraceEntry(
        step.step_number,
        LABELS.get(name, 'Thực hiện thao tác'),
        detail,
        status,
        stage=stage,
        evidence_ref=ev_ref or res_id,
        resource_id=res_id,
        artifact_id=art_id,
        revision=art_rev,
    )


def build_reasoning_flow(
    steps: Sequence[Any] = (),
    *,
    contract: Optional[Any] = None,
    reconciliation: Optional[Any] = None,
    journal: Optional[Any] = None,
    finder_intent: Optional[Any] = None,
    finder_hits_count: Optional[int] = None,
    direct_artifact: Optional[Any] = None,
    active_phase: str = '',
    active_label: str = '',
    streaming_chars: int = 0,
    error: Optional[str] = None,
) -> List[TraceEntry]:
    """
    Construct a compact, grounded public reasoning flow:
      hiểu yêu cầu → tìm/đọc nguồn → kiểm tra điều kiện → kết quả/hỏi làm rõ.

    Invariants:
    - Never accesses private `thought`, `raw_completion`, or `model_input`.
    - Distinguishes `proposed`, `running`, `found`, `read`, `verified_pass`,
      `verified_fail`, `unchecked`, `waiting`, `error`, and `cancelled`.
    - Every state is anchored to an observed step, receipt, artifact revision,
      or deterministic FinderIntentPlan. Unexecuted plans stay `proposed`.
    """
    flow: List[TraceEntry] = []
    seq = 1

    # 1. Deterministic Finder Intent Flow (0 model calls)
    if finder_intent is not None and not steps and direct_artifact is None:
        chips = list(getattr(finder_intent, 'interpretation_chips', ()) or ())
        action = getattr(finder_intent, 'action', 'find')
        has_structured = bool(
            chips
            or getattr(finder_intent, 'needs_clarification', False)
            or action in ('open_app', 'negated_open')
            or getattr(finder_intent, 'slide_rule', False)
            or getattr(finder_intent, 'report_rule', False)
            or getattr(finder_intent, 'date_min', None) is not None
        )
        if not has_structured:
            return []

        understand_title = (
            'Ghi nhận lệnh phủ định'
            if action == 'negated_open'
            else 'Nhận diện yêu cầu mở ứng dụng'
            if action == 'open_app'
            else 'Hiểu điều kiện tìm kiếm'
        )
        understand_detail = ' · '.join(chips) if chips else str(getattr(finder_intent, 'raw_query', ''))
        flow.append(
            TraceEntry(
                number=seq,
                title=understand_title,
                detail=understand_detail,
                status='found',
                stage='understand',
                evidence_ref='intent:finder_plan',
            )
        )
        seq += 1

        if getattr(finder_intent, 'needs_clarification', False):
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Cần làm rõ yêu cầu',
                    detail=str(getattr(finder_intent, 'clarification_reason', '') or 'Cần thêm thông tin để lọc chính xác.'),
                    status='waiting',
                    stage='clarify',
                    evidence_ref='intent:needs_clarification',
                )
            )
            return flow

        if action == 'negated_open':
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Giữ nguyên trạng thái (không mở ứng dụng)',
                    detail=str(getattr(finder_intent, 'clarification_reason', '') or 'Đã chặn thao tác mở theo yêu cầu phủ định.'),
                    status='done',
                    stage='result',
                    evidence_ref='intent:negated_open',
                )
            )
            return flow

        count = int(finder_hits_count or 0)
        if action == 'open_app':
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Đối chiếu danh mục ứng dụng macOS',
                    detail=(
                        f"Tìm thấy {count} ứng viên khớp · đang gợi ý, chỉ mở khi bạn nhấn Enter hoặc chọn Mở."
                        if count > 0
                        else "Chưa tìm thấy gói .app khớp trong danh mục ứng dụng."
                    ),
                    status='proposed' if count > 0 else 'unchecked',
                    stage='search',
                    evidence_ref=f"catalog:hits={count}",
                )
            )
        else:
            scope_note = str(getattr(finder_intent, 'scope_note', '') or '').strip()
            detail = f"Khớp {count} nguồn theo metadata/chỉ mục · chưa đọc toàn bộ nội dung bên trong."
            if scope_note:
                detail = f"{detail} {scope_note}"
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Lọc ứng viên trong chỉ mục',
                    detail=detail,
                    status='found' if count > 0 else 'unchecked',
                    stage='search',
                    evidence_ref=f"index:hits={count}",
                )
            )
        return flow

    # 2. Direct Artifact Operation Flow (e.g. open_application disambiguation or launch receipt)
    if direct_artifact is not None and not steps:
        kind = getattr(direct_artifact, 'kind', '')
        payload = getattr(direct_artifact, 'payload', {}) if isinstance(getattr(direct_artifact, 'payload', None), dict) else {}
        art_ref = f"{direct_artifact.id}@v{direct_artifact.revision}"
        if kind == 'input_request':
            raw_cands = payload.get('candidate_choices') or payload.get('candidates')
            candidates = raw_cands if isinstance(raw_cands, list) else []
            prompt = str(payload.get('prompt') or 'Cần bạn chọn hoặc bổ sung thông tin.')
            if candidates:
                names = ', '.join(
                    f"{c.get('name', 'App')} ({c.get('path', '')})"
                    for c in candidates[:3]
                    if isinstance(c, dict)
                )
                flow.append(
                    TraceEntry(
                        number=seq,
                        title='Tìm thấy nhiều bản cài đặt ứng dụng',
                        detail=f"Có {len(candidates)} ứng viên trên ổ đĩa: {names}",
                        status='found',
                        stage='search',
                        evidence_ref=art_ref,
                        artifact_id=direct_artifact.id,
                        revision=direct_artifact.revision,
                    )
                )
                seq += 1
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Chờ bạn chọn ứng dụng cần mở' if candidates else 'Chờ bổ sung thông tin',
                    detail=f"{prompt} (Chưa mở ứng dụng nào)",
                    status='waiting',
                    stage='clarify',
                    evidence_ref=art_ref,
                    artifact_id=direct_artifact.id,
                    revision=direct_artifact.revision,
                )
            )
            return flow

        if kind == 'application_launch':
            app_name = str(payload.get('name') or direct_artifact.title or 'Ứng dụng')
            bundle_id = str(payload.get('bundle_id') or '')
            path_str = str(payload.get('path') or '')
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Kiểm tra gói ứng dụng trên ổ đĩa',
                    detail=f"Đã xác thực .app, Info.plist và tệp thực thi ({bundle_id or path_str}).",
                    status='verified_pass',
                    stage='verify',
                    evidence_ref=art_ref,
                    resource_id=str(payload.get('resource_id') or path_str),
                    artifact_id=direct_artifact.id,
                    revision=direct_artifact.revision,
                )
            )
            seq += 1
            flow.append(
                TraceEntry(
                    number=seq,
                    title=f"Đã gửi yêu cầu mở {app_name} tới macOS",
                    detail="Hệ điều hành đã nhận lệnh khởi chạy (.app) · không đồng nghĩa đã đăng nhập hay vào trong màn hình trò chơi.",
                    status='done',
                    stage='result',
                    evidence_ref=art_ref,
                    resource_id=str(payload.get('resource_id') or path_str),
                    artifact_id=direct_artifact.id,
                    revision=direct_artifact.revision,
                )
            )
            return flow

    # 3. Runtime Execution & Contract Reconciliation Flow
    receipts = getattr(journal, 'receipts', []) if journal is not None else []
    receipt_by_call = {
        getattr(r, 'operation_call_id', ''): r
        for r in receipts
        if getattr(r, 'operation_call_id', None)
    }

    for step in steps:
        base_entry = summarize_step(step)
        call_id = f"step-{getattr(step, 'step_number', 0)}"
        rcpt = receipt_by_call.get(call_id)
        rcpt_id = getattr(rcpt, 'receipt_id', '') if rcpt is not None else ''
        name = getattr(step, 'tool_name', None)
        res = getattr(step, 'tool_result', None)

        # Refine status to distinguish `found` vs `read` vs `proposed` vs `done`
        refined_status = base_entry.status
        if refined_status == 'done':
            if name in ('search_documents', 'search_book_pages', 'search_birth_places'):
                refined_status = 'found'
            elif name in ('read_document', 'read_book_page', 'read_web_page', 'inspect_artifact') and isinstance(res, dict) and (res.get('found') or res.get('content')):
                refined_status = 'read'

        ev = base_entry.evidence_ref
        if rcpt_id and ev:
            ev = f"{rcpt_id} · {ev}"
        elif rcpt_id:
            ev = rcpt_id

        flow.append(
            TraceEntry(
                number=seq,
                title=base_entry.title,
                detail=base_entry.detail,
                status=refined_status,
                stage=base_entry.stage or _stage_for_tool(name),
                evidence_ref=ev,
                receipt_id=rcpt_id,
                resource_id=base_entry.resource_id,
                artifact_id=base_entry.artifact_id,
                revision=base_entry.revision,
            )
        )
        seq += 1

    # Check declared TurnContract outcomes for unexecuted / in-progress steps
    outcomes = list(getattr(contract, 'outcomes', ()) or ()) if contract is not None else []
    matched_rcpt_ids = set(getattr(reconciliation, 'matched_receipts', ()) or ()) if reconciliation is not None else set()
    unmet_map = {
        u.get('outcome_id'): u
        for u in (getattr(reconciliation, 'unmet_outcomes', ()) or [])
        if isinstance(u, dict) and u.get('outcome_id')
    } if reconciliation is not None else {}

    observed_ops = {
        getattr(s, 'tool_name', None)
        for s in steps
        if getattr(s, 'tool_name', None) and not getattr(s, 'error', None)
        and not (isinstance(getattr(s, 'tool_result', None), dict) and (getattr(s, 'tool_result', {}).get('error') or getattr(s, 'tool_result', {}).get('found') is False))
    }
    has_final_answer = any(
        not getattr(s, 'tool_name', None)
        and not getattr(s, 'error', None)
        and not getattr(s, 'verification', None)
        and not (isinstance(getattr(s, 'tool_result', None), dict) and getattr(s, 'tool_result', {}).get('phase') == 'initial_plan')
        for s in steps
    )

    if active_phase == 'working':
        # Show currently running or proposed remaining steps from contract
        shown_running = False
        for outcome in outcomes:
            kind = getattr(outcome, 'kind', '')
            eff = getattr(outcome, 'effect_type', '')
            desc = str(getattr(outcome, 'description', '') or eff or kind)
            if kind == 'registered_effect' and eff in observed_ops:
                continue
            if kind == 'response' and has_final_answer:
                continue
            if not shown_running:
                shown_running = True
                run_detail = active_label or desc
                if kind == 'response' and streaming_chars > 0:
                    run_detail = f"Đang ghi câu trả lời trực tiếp ({streaming_chars:,} ký tự)…"
                flow.append(
                    TraceEntry(
                        number=seq,
                        title=desc if desc else (active_label or 'Đang thực hiện bước tiếp theo'),
                        detail=run_detail,
                        status='running',
                        stage='result' if kind == 'response' else _stage_for_tool(eff),
                        evidence_ref=f"contract:{getattr(outcome, 'outcome_id', '')}",
                    )
                )
            else:
                flow.append(
                    TraceEntry(
                        number=seq,
                        title=f"Dự định: {desc}",
                        detail="Kế hoạch đã khai · chưa thực thi",
                        status='proposed',
                        stage='plan',
                        evidence_ref=f"contract:{getattr(outcome, 'outcome_id', '')}",
                    )
                )
            seq += 1

        if not outcomes and active_label:
            flow.append(
                TraceEntry(
                    number=seq,
                    title=active_label,
                    detail=(
                        f"Đang ghi câu trả lời ({streaming_chars:,} ký tự)…"
                        if streaming_chars > 0
                        else "Đang xử lý yêu cầu hiện tại…"
                    ),
                    status='running',
                    stage='result' if streaming_chars > 0 else 'understand',
                )
            )
            seq += 1
    else:
        # Turn has finished/cancelled/errored: surface any unexecuted contract outcomes as `proposed` (never `done`)
        for outcome in outcomes:
            oid = getattr(outcome, 'outcome_id', '')
            if oid in unmet_map:
                unmet_info = unmet_map[oid]
                desc = str(getattr(outcome, 'description', '') or unmet_info.get('description') or oid)
                reason_code = str(unmet_info.get('reason') or 'unmet')
                flow.append(
                    TraceEntry(
                        number=seq,
                        title=f"Dự định chưa thực thi: {desc}",
                        detail=f"Chưa chạy ({reason_code}) · không tính là đã hoàn thành.",
                        status='proposed',
                        stage='plan',
                        evidence_ref=f"contract:{oid}",
                    )
                )
                seq += 1

    # Append grounded reconciliation / verification check when turn has reconciliation
    if reconciliation is not None:
        lifecycle = getattr(reconciliation, 'lifecycle', '')
        comp = getattr(reconciliation, 'declared_scope_completion', 'unchecked')
        qual = getattr(reconciliation, 'scoped_quality', 'not_checked')
        rcpt_list = list(matched_rcpt_ids)
        rcpt_summary = ', '.join(rcpt_list[:2])

        if lifecycle == 'cancelled' or active_phase == 'cancelled':
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Đã dừng theo yêu cầu',
                    detail='Các dữ kiện đã đọc được giữ lại trên bàn; phần việc chưa chạy đã hủy.',
                    status='cancelled',
                    stage='verify',
                    evidence_ref=rcpt_summary,
                )
            )
        elif lifecycle == 'needs_input' or active_phase == 'waiting':
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Chờ thông tin bổ sung',
                    detail=str(getattr(reconciliation, 'summary', '') or 'Đang chờ bạn xác nhận hoặc chọn ứng viên.'),
                    status='waiting',
                    stage='clarify',
                    evidence_ref=rcpt_summary,
                )
            )
        elif qual == 'FAIL' or error == 'verification_failed':
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Kiểm tra điều kiện chưa đạt',
                    detail=str(getattr(reconciliation, 'summary', '') or 'Kết luận chưa khớp với dữ kiện kiểm chứng.'),
                    status='verified_fail',
                    stage='verify',
                    evidence_ref=rcpt_summary,
                )
            )
        elif qual == 'PASS':
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Đã kiểm chứng trong phạm vi',
                    detail=f"Đối chiếu đạt ({rcpt_summary or 'verification:PASS'}) · chỉ xác nhận phạm vi đã kiểm tra.",
                    status='verified_pass',
                    stage='verify',
                    evidence_ref=rcpt_summary or 'verification:PASS',
                )
            )
        elif comp == 'satisfied' and rcpt_list:
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Đủ điều kiện hoàn tất theo biên nhận',
                    detail=(
                        f"Khớp biên nhận ({rcpt_summary}) · xác nhận đã đọc nguồn và trả lời, "
                        "không tự chứng minh suy diễn ngoài phần đã đọc."
                    ),
                    status='verified_pass',
                    stage='verify',
                    evidence_ref=rcpt_summary,
                )
            )
        elif lifecycle == 'failed' or error:
            flow.append(
                TraceEntry(
                    number=seq,
                    title='Chưa hoàn tất yêu cầu',
                    detail=str(getattr(reconciliation, 'summary', '') or error or 'Còn bước chưa thực hiện được.'),
                    status='error',
                    stage='verify',
                    evidence_ref=rcpt_summary,
                )
            )
    elif active_phase == 'cancelled' or error == 'cancelled':
        flow.append(
            TraceEntry(
                number=seq,
                title='Đã dừng theo yêu cầu',
                detail='Các dữ kiện đã đọc được giữ lại trên bàn; phần việc chưa chạy đã hủy.',
                status='cancelled',
                stage='verify',
            )
        )
    elif active_phase == 'error' and error:
        flow.append(
            TraceEntry(
                number=seq,
                title='Chưa hoàn tất yêu cầu',
                detail=str(error),
                status='error',
                stage='verify',
            )
        )

    return flow

