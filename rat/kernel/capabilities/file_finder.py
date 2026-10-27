"""File-only reasoning capability over the shared HybridFinder provider."""
import subprocess

from rat.kernel.contracts import InputRequest
from rat.kernel.registry import Capability, OperationDefinition
from rat.engine.verification import VerificationReport, VerificationStatus
from rat.os.system_process import system_environment


class ScopedFinderVerifier:
    def __init__(self, finder):
        self.finder = finder

    def check_execution(self, evidence):
        result = evidence.result
        try:
            assert result['hit_count'] == len(result['hits'])
            assert result['scope_version'] == self.finder.scopes.version
            for hit in result['hits']:
                self.finder.scopes.verify(hit['path'], hit['identity'])
            status = VerificationStatus.PASS
        except (KeyError, TypeError, AssertionError, OSError, ValueError):
            status = VerificationStatus.FAIL
        return VerificationReport(status, 'scoped_file_access',
            'Kiểm tra file tồn tại, quyền đọc, scope và identity; không bảo chứng đúng ý định tìm kiếm.',
            (evidence.id,), checked=('file_identity', 'readability', 'scope'))

    def check_answer(self, goal, answer, evidence):
        return None


def create_file_finder_capability(finder):
    capability = Capability('finder', 'Tìm file', 'Tìm file trong các thư mục người dùng đã chọn.')
    filters = {'type': 'object', 'properties': {
        'extensions': {'type': 'array', 'maxItems': 20, 'items': {'type': 'string', 'maxLength': 16}},
        'excluded_extensions': {'type': 'array', 'maxItems': 20, 'items': {'type': 'string', 'maxLength': 16}},
        'date_field': {'type': 'string', 'enum': ['created', 'modified']},
        'from': {'type': 'string', 'maxLength': 40}, 'to': {'type': 'string', 'maxLength': 40},
        'sort': {'type': 'string', 'enum': ['relevance', 'newest', 'oldest']}}}

    def find(args, **context):
        if not finder.scopes.roots:
            return InputRequest('find_files', missing_fields=[{'name': 'folder', 'required': True}],
                                prompt='Chọn ít nhất một thư mục trong Cài đặt để bắt đầu tìm file.')
        return finder.search(args['query'], limit=args.get('limit', 8), filters=args.get('filters'),
                             mode=args.get('mode', 'auto'), should_cancel=context.get('should_cancel') or (lambda: False))

    capability.register_operation(OperationDefinition('find_files', 'Find local files using real Spotlight and optional local semantic evidence. Never invent paths.',
        {'type': 'object', 'properties': {'query': {'type': 'string', 'maxLength': 2000},
            'filters': filters, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
            'mode': {'type': 'string', 'enum': ['auto', 'metadata', 'hybrid']}}, 'required': ['query']},
        find, artifact_kind='finder_results', verifier=ScopedFinderVerifier(finder),
        observation_formatter=lambda d: {'status': d.get('status'), 'query': d.get('query'),
            'hits': [{k: h[k] for k in ('resource_id', 'title', 'match_sources')} for h in d.get('hits', [])],
            'coverage': d.get('coverage'), 'provider_errors': d.get('provider_errors')}))

    def action(reveal, args, context):
        if not context.get('user_initiated'):
            raise ValueError('open_requires_user_action')
        artifact = context['target_artifact']
        if artifact.payload['scope_version'] != finder.scopes.version:
            raise ValueError('scope_revoked')
        hit = next((h for h in artifact.payload['hits'] if h['resource_id'] == args['resource_id']), None)
        if hit is None:
            raise ValueError('unknown_resource')
        path, _, _ = finder.scopes.verify(hit['path'], hit['identity'])
        subprocess.run(['/usr/bin/open', *(['-R'] if reveal else []), str(path)],
                       check=True, timeout=5, env=system_environment(), stdin=subprocess.DEVNULL)
        return {'status': 'complete', 'result': 'Đã gửi yêu cầu đến Finder.' if reveal else 'Đã gửi yêu cầu mở file đến macOS.'}

    for name, reveal in [('open_file', False), ('reveal_file', True)]:
        capability.register_operation(OperationDefinition(name, 'Open or reveal a previously verified file after user click.',
            {'type': 'object', 'properties': {'resource_id': {'type': 'string', 'maxLength': 128}},
             'required': ['resource_id']},
            lambda args, _reveal=reveal, **context: action(_reveal, args, context),
            target_kind='finder_results', model_visible=False))

    def index(args, **context):
        if not context.get('user_initiated'):
            raise ValueError('index_requires_user_action')
        if finder.semantic is None or not finder.scopes.roots:
            raise ValueError('semantic_or_roots_unavailable')
        return finder.semantic.index(context.get('should_cancel') or (lambda: False), context.get('progress') or (lambda s: None))
    if finder.semantic is not None:
        capability.register_operation(OperationDefinition('index_files', 'Explicitly rebuild the local semantic index.',
            {'type': 'object', 'properties': {}}, index, artifact_kind='index_receipt', model_visible=False))
    return capability
