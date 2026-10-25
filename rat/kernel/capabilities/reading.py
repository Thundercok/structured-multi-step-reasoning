"""Reading preparation and synthesis tools shared by agent execution and explicit UI actions."""
from pathlib import Path

from rat.kernel.registry import Capability, OperationDefinition


def create_reading_capability():
    capability = Capability('reading', 'Bàn xem', 'Chuẩn bị dữ kiện trải bài và hồ sơ lá số; soạn bản luận đang chờ nối Agent/model.')

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
        # No interpretation model is connected to this operation yet. Keep the
        # dispatcher failure observable; a prototype must not become an answer.
        raise RuntimeError('model_unavailable: Chưa nối vòng Agent/model cho bản luận; chưa tạo bản luận.')

    capability.register_operation(OperationDefinition(
        name='prepare_reading_spread',
        description='Record the exact tarot cards supplied by the user, preserving order, reversals and jumpers. Never invent or randomly draw cards. Use the resulting artifact as evidence before interpreting.',
        parameters={'type': 'object', 'additionalProperties': False,
                    'properties': {'text': {'type': 'string', 'maxLength': 2000}}, 'required': ['text']},
        handler=prepare, artifact_kind='reading_spread',
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
        description='Request an interpretation draft. Currently unavailable until an Agent/model loop is connected; returns an error and never substitutes a template for model reasoning.',
        parameters={'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'maxLength': 2000},
                    }},
        handler=synthesize, artifact_kind='reading_draft',
    ))
    return capability
