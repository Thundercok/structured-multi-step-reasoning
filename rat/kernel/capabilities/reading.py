"""Reading preparation and synthesis tools shared by agent execution and explicit UI actions."""
from pathlib import Path

from rat.engine.verification import ReadingVerifier
from rat.kernel.registry import Capability, OperationDefinition


def create_reading_capability():
    capability = Capability('reading', 'Bàn xem', 'Chuẩn bị dữ kiện trải bài và hồ sơ lá số; soạn bản luận qua vòng Agent/model.')
    verifier = ReadingVerifier()

    def prepare(args, **context):
        from rat.engine.reading_session import parse_cards
        return {'cards': parse_cards(args['text']), 'origin': 'supplied_cards_not_random_draw'}

    def load(args, **context):
        from rat.engine.reading_session import load_natal_profile
        path = Path(args['file_path']).resolve()
        selected = context.get('selected_document_path')
        if not selected or path != Path(selected).resolve():
            raise ValueError('Cần người dùng chọn hồ sơ lá số trước; không tự đoán đường dẫn.')
        return load_natal_profile(path)

    def synthesize(args, **context):
        model_client = context.get('model_client')
        runtime = context.get('runtime')
        if model_client is None and runtime is not None:
            model_client = getattr(runtime, 'document_model_client', None) or getattr(runtime, 'model_client', None)

        if model_client is None:
            raise RuntimeError('model_unavailable: Chưa nối vòng Agent/model cho bản luận; chưa tạo bản luận.')

        query = args.get('query') or context.get('query') or 'Soạn bản luận cho trải bài hiện tại'
        cards = args.get('cards') or context.get('reading_cards') or []
        chart = args.get('chart') or context.get('reading_chart') or {}
        context_notes = context.get('context_notes') or ''

        if not cards and not chart:
            raise ValueError('Hãy đặt bài lên bàn hoặc chọn hồ sơ lá số trước khi soạn bản luận.')

        card_lines = []
        for c in cards:
            pos_label = "Lá rơi (jumper)" if c.get("jumper") else f"Vị trí {c.get('position')}"
            orient = "Ngược (reversed)" if c.get("reversed") else "Xuôi (upright)"
            card_lines.append(f"- {pos_label}: {c.get('title')} ({orient})")
        card_desc = "\n".join(card_lines) if card_lines else "Không có trải bài Tarot."

        positions = chart.get('positions') or []
        pos_lines = [f"- {p.get('name')}: {p.get('position')}" for p in positions]
        chart_desc = "\n".join(pos_lines) if pos_lines else "Không có hồ sơ lá số."

        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý phân tích trải bài Tarot và hồ sơ chiêm tinh trong RAT.\n"
                    "Các lá bài và tọa độ hành tinh được cung cấp là dữ kiện quan sát thực tế (input_fact), "
                    "không được tự bịa thêm lá bài hay tọa độ khác.\n"
                    "Tách bạch giữa dữ kiện đầu vào, các góc chiếu/tọa độ đã tính, và phần luận giải.\n"
                    "Phần diễn giải mang tính chiêm nghiệm biểu tượng, không khẳng định tương lai như sự kiện lịch sử.\n"
                    "Trình bày mạch lạc bằng tiếng Việt."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Câu hỏi / Trọng tâm: {query}\n\n"
                    f"Trải bài Tarot:\n{card_desc}\n\n"
                    f"Tọa độ lá số chiêm tinh:\n{chart_desc}\n\n"
                    f"Ghi chú bổ sung: {context_notes or 'Không có'}\n\n"
                    "Hãy soạn bản luận chi tiết có cấu trúc dựa trên các dữ kiện trên."
                ),
            },
        ]

        meta = model_client.chat_with_meta(messages, [], max_tokens=1000, thinking=False)
        message = (meta.get("message") or {}) if isinstance(meta, dict) else {}
        content = message.get("content", "")
        error = meta.get("error") if isinstance(meta, dict) else None

        if error or not content.strip():
            raise RuntimeError(f"model_generation_failed: {error or 'Model trả về phản hồi rỗng.'}")

        return {
            "title": f"Bản luận: {query[:60]}",
            "query": query,
            "cards": cards,
            "chart_positions": positions,
            "draft_markdown": content.strip(),
            "cot_steps": [
                {"step": 1, "thought": "Tổng hợp các lá bài và tọa độ hành tinh đã quan sát", "status": "completed"},
                {"step": 2, "thought": "Soạn bản luận giải thích ý nghĩa biểu tượng theo ngữ cảnh", "status": "completed"},
            ],
            "verification_status": "UNKNOWN",
            "verification_scope": "Chưa xác minh nội dung diễn giải (diễn giải mang tính biểu tượng/tham khảo)",
            "user_edited": False,
        }

    capability.register_operation(OperationDefinition(
        name='prepare_reading_spread',
        description='Record the exact tarot cards supplied by the user, preserving order, reversals and jumpers. Never invent or randomly draw cards. Use the resulting artifact as evidence before interpreting.',
        parameters={'type': 'object', 'additionalProperties': False,
                    'properties': {'text': {'type': 'string', 'maxLength': 2000}}, 'required': ['text']},
        handler=prepare, artifact_kind='reading_spread',
        verifier=verifier,
        result_contract={'type': 'object', 'properties': {'cards': {'type': 'array', 'maxItems': 12,
                         'items': {'type': 'object', 'properties': {
                             'title': {'type': 'string'}, 'suit': {'type': 'string'}, 'numeral': {'type': 'string'},
                             'reversed': {'type': 'boolean'}, 'jumper': {'type': 'boolean'},
                             'position': {'type': 'integer', 'minimum': 0, 'maximum': 12},
                         }, 'required': ['title', 'suit', 'numeral', 'reversed', 'jumper', 'position']}},
                         'origin': {'type': 'string'}},
                         'required': ['cards', 'origin']},
    ))
    capability.register_operation(OperationDefinition(
        name='load_reading_profile',
        description='Read an explicitly selected local rat-natal-v1 birth profile and recalculate its chart. Never trust imported planetary positions or guess a profile path. Requires selected_document_path from the user selection context.',
        parameters={'type': 'object', 'additionalProperties': False,
                    'properties': {'file_path': {'type': 'string'}}, 'required': ['file_path']},
        handler=load, artifact_kind='reading_natal_profile',
        verifier=verifier,
        result_contract={'type': 'object', 'properties': {
            **{k: {'type': 'string'} for k in ('name', 'date', 'time', 'place', 'fileName')},
            'positions': {'type': 'array', 'minItems': 5, 'maxItems': 5,
                          'items': {'type': 'object', 'properties': {
                              'name': {'type': 'string'}, 'position': {'type': 'string'}},
                              'required': ['name', 'position']}},
            'notices': {'type': 'array', 'maxItems': 30, 'items': {'type': 'string'}},
            'chart': {},  # Structured chart is validated by calculate_chart.
        }, 'required': ['name', 'date', 'time', 'place', 'fileName', 'positions', 'chart', 'notices']},
    ))
    capability.register_operation(OperationDefinition(
        name='synthesize_reading_draft',
        description='Request an interpretation draft from supplied cards or chart using the Agent/model loop. Separate observed facts from symbolic interpretation.',
        parameters={'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'maxLength': 2000},
                    }},
        handler=synthesize, artifact_kind='reading_draft',
        verifier=verifier,
    ))
    return capability
