"""Registered standard presentation factories for the bundled capabilities."""
from rat.kernel.view_spec import ViewSpec, ViewBlock

def view_natal_chart(artifact, context) -> ViewSpec:
    from rat.astrology.chart import degree_text, SIGNS
    chart_data = artifact.payload.get('chart', artifact.payload)
    birth = chart_data.get('birth', artifact.inputs)
    name = birth.get('name', 'Lá số cá nhân')
    date = birth.get('date', '')
    time_val = birth.get('time', '') if birth.get('time_known', True) else 'Giờ sinh chưa rõ'
    place = birth.get('place', '')
    positions = chart_data.get('positions', [])
    angles = chart_data.get('angles', {})
    sun = next((p.get('sign') for p in positions if p.get('id') == 'sun'), 'Mặt Trời')
    moon = next((p.get('sign') for p in positions if p.get('id') == 'moon'), 'Mặt Trăng')
    asc = angles.get('ASC')
    asc_sign = ''
    if asc is not None and isinstance(asc, (int, float)):
        sign_idx = int(asc // 30) % 12
        asc_sign = SIGNS[sign_idx][0]
    blocks: List[ViewBlock] = []
    blocks.append(ViewBlock(type='summary', data={'title': f'✧ {name} · {date} {time_val} ({place})', 'text': f'Mặt Trời: {sun} · Mặt Trăng: {moon}' + (f' · Cung Mọc: {asc_sign}' if asc_sign else ''), 'badge': f'Phiên bản {artifact.revision}'}))
    blocks.append(ViewBlock(type='resource', data={'resource': 'wheel', 'field': 'chart'}))
    pos_rows = []
    for p in positions:
        pos_rows.append([p.get('name', ''), p.get('glyph', ''), degree_text(p['longitude'], seconds=True), f'Nhà {p.get('house')}' if p.get('house') else '—'])
    blocks.append(ViewBlock(type='details', data={'title': 'Vị trí thiên thể', 'table_headers': ['Thiên thể', 'Ký hiệu', 'Tọa độ', 'Nhà'], 'table_rows': pos_rows}))
    if chart_data.get('notices'):
        blocks.insert(1, ViewBlock('summary', {'text': '\n'.join(chart_data['notices'])}))
    if chart_data.get('cusps'):
        blocks.append(ViewBlock('details', {'title': 'Các nhà', 'table_headers': ['Nhà', 'Đỉnh nhà'],
            'table_rows': [[str(i + 1), degree_text(value, seconds=True)] for i, value in enumerate(chart_data['cusps'])]}))
    blocks.append(ViewBlock('details', {'title': 'Góc chiếu', 'table_headers': ['Điểm', 'Góc', 'Điểm', 'Orb'],
        'table_rows': [[a['first'], a['name'], a['second'], f"{a['orb']:.4f}°"] for a in chart_data.get('aspects', [])]}))
    return ViewSpec(schema_version=1, artifact_id=artifact.id, revision=artifact.revision, title=f'Lá số · {name}', blocks=blocks)

def view_schedule(artifact, context) -> ViewSpec:
    items = artifact.payload.get('items', [])
    day_label = artifact.inputs.get('target_date', 'Hôm nay')
    rows = []
    for s in items:
        rows.append([s.get('time', ''), s.get('course_name', ''), s.get('room', ''), s.get('instructor', '')])
    blocks = [ViewBlock(type='summary', data={'title': f'Lịch học · {day_label}', 'text': f'Có {len(items)} ca học được ghi nhận.'}), ViewBlock(type='table', data={'headers': ['Thời gian', 'Môn học', 'Phòng', 'Giảng viên'], 'rows': rows, 'items': items})]
    return ViewSpec(schema_version=1, artifact_id=artifact.id, revision=artifact.revision, title=f'Lịch học · {day_label}', blocks=blocks)

def view_document_search(artifact, context) -> ViewSpec:
    results = artifact.payload.get('items', artifact.payload.get('results', []))
    query = artifact.inputs.get('query', '')
    file_rows = []
    for f in results:
        file_rows.append([f.get('filename', ''), f.get('snippet', ''), f.get('path', '')])
    blocks = [ViewBlock(type='summary', data={'title': f'Tìm kiếm tệp: {query}', 'text': f'Tìm thấy {len(results)} tệp liên quan trong chỉ mục.'}), ViewBlock(type='table', data={'headers': ['Tên tệp', 'Nội dung', 'Đường dẫn'], 'rows': file_rows, 'files': results})]
    return ViewSpec(schema_version=1, artifact_id=artifact.id, revision=artifact.revision, title=f'Tài liệu · {query}', blocks=blocks)

def view_document_content(artifact, context) -> ViewSpec:
    doc = artifact.payload
    filename = doc.get('filename', 'Tài liệu')
    content = doc.get('content', '')
    chars = doc.get('total_chars', len(content))
    blocks = [ViewBlock(type='summary', data={'title': f'Nội dung tệp · {filename}', 'text': f'Đã đọc {len(content)} / {chars} ký tự.'}), ViewBlock(type='details', data={'title': 'Trích xuất văn bản', 'content': content})]
    return ViewSpec(schema_version=1, artifact_id=artifact.id, revision=artifact.revision, title=f'Đọc tệp · {filename}', blocks=blocks)

def view_document_file(artifact, context) -> ViewSpec:
    data = artifact.payload
    return ViewSpec(1, artifact.id, artifact.revision, title=data['filename'], blocks=[
        ViewBlock('summary', {'title': 'Tệp của bạn', 'text': data['filename']}),
    ])

def view_book_page_search(artifact, context) -> ViewSpec:
    data = artifact.payload
    title = f"Trang sách · {data['filename']}"
    start, end = data['searched_range']
    text = f"Tìm thấy {data['matched_pages']} trang khớp trong phạm vi PDF {start}–{end}."
    if data['results_truncated']:
        text += f" Đang hiển thị {len(data['items'])} trang."
    if data['next_start_page']:
        text += f" Còn trang chưa tìm từ {data['next_start_page']}."
    if data['textless_pages'] or data['unreadable_pages']:
        text += f" {len(data['textless_pages'])} trang không có văn bản; {len(data['unreadable_pages'])} trang lỗi đọc."
    return ViewSpec(1, artifact.id, artifact.revision, title=title, blocks=[
        ViewBlock('summary', {'title': title, 'text': text}),
        ViewBlock('table', {'headers': ['Trang PDF', 'Nhãn PDF', 'Đoạn khớp'],
                           'rows': [[p['page'], p['page_label'], p['snippet']] for p in data['items']]}),
        ViewBlock('details', {'title': 'Phạm vi và nguồn', 'content': data['path'] + '\n' + data['notice']}),
    ])

def view_book_page_content(artifact, context) -> ViewSpec:
    data = artifact.payload
    title = f"{data['filename']} · Trang PDF {data['page']} · Nhãn {data['page_label']}"
    text = f"Đã đọc {len(data['content'])}/{data['total_chars']} ký tự."
    if data['truncated']:
        text += ' Nội dung đã cắt ngắn.'
    return ViewSpec(1, artifact.id, artifact.revision, title=title, blocks=[
        ViewBlock('summary', {'title': title, 'text': text}),
        ViewBlock('details', {'title': 'Nội dung trang', 'content': data['content']}),
        ViewBlock('details', {'title': 'Nguồn trích dẫn', 'content': data['path'] + '\n' + data['notice']}),
    ])

def view_input_request(artifact, context) -> ViewSpec:
    req_data = artifact.payload
    prompt = req_data.get('prompt', 'Vui lòng nhập thêm thông tin.')
    missing = req_data.get('missing_fields', [])
    candidates = req_data.get('candidate_choices')
    supplied = req_data.get('supplied_inputs', {})
    blocks = [ViewBlock(type='summary', data={'text': prompt}), ViewBlock(type='input_form', data={'operation_name': req_data.get('operation_name', ''), 'missing_fields': missing, 'candidate_choices': candidates, 'supplied_inputs': supplied})]
    return ViewSpec(schema_version=1, artifact_id=artifact.id, revision=artifact.revision, title='Nhập thông tin', blocks=blocks)

def view_generic(artifact, context) -> ViewSpec:
    blocks = [ViewBlock(type='summary', data={'title': artifact.title or f'{artifact.kind} #{artifact.id}', 'text': f'Loại: {artifact.kind} · Phiên bản {artifact.revision}'}), ViewBlock(type='details', data={'title': 'Dữ liệu kết quả', 'content': str(artifact.payload)})]
    return ViewSpec(schema_version=1, artifact_id=artifact.id, revision=artifact.revision, title=artifact.title or artifact.kind, blocks=blocks)

def view_file_export(artifact, context):
    data = artifact.payload
    return ViewSpec(1, artifact.id, artifact.revision, title='Đã lưu lá số', blocks=[ViewBlock('summary', {'title': 'Đã lưu ' + data.get('filename', 'tệp'), 'text': data.get('exported_path', '')})])

def view_application_launch(artifact, context) -> ViewSpec:
    data = artifact.payload
    name = data.get('name', 'Ứng dụng')
    status_label = data.get('status_label', 'Đã gửi yêu cầu mở ứng dụng tới macOS')
    note = data.get('verification_note', '')
    path = data.get('path', '')
    bundle_id = data.get('bundle_id', '')
    version = data.get('version', '')
    meta_parts = [p for p in (path, bundle_id, f'v{version}' if version else '') if p]
    return ViewSpec(
        schema_version=1,
        artifact_id=artifact.id,
        revision=artifact.revision,
        title=f'Mở ứng dụng · {name}',
        blocks=[
            ViewBlock(
                'summary',
                {
                    'title': f'{name} · {status_label}',
                    'text': (' · '.join(meta_parts) + ('\n' + note if note else '')).strip(),
                    'badge': data.get('launch_status', 'os_launch_accepted'),
                },
            ),
        ],
    )

def view_web_page_snapshot(artifact, context) -> ViewSpec:
    data = artifact.payload
    url = data.get('final_url') or data.get('requested_url') or 'Trang web'
    title = data.get('title', f"Web · {url}")
    status = data.get('status_code', 'unknown')
    content = data.get('content', '')
    chars = len(content)
    text = f"URL: {url} · HTTP {status} · {chars} ký tự."
    if data.get('truncated'):
        text += " (Đã cắt ngắn)."
    blocks = [
        ViewBlock('summary', {'title': title, 'text': text}),
        ViewBlock('details', {'title': 'Nội dung trích xuất', 'content': content}),
        ViewBlock('details', {'title': 'Nguồn & Bản chụp', 'content': f"URL: {url}\nBản chụp SHA256: {data.get('content_hash', '')}\nEngine: {data.get('engine', 'spider')} {data.get('engine_version', '')}"}),
    ]
    return ViewSpec(1, artifact.id, artifact.revision, title=title, blocks=blocks)

