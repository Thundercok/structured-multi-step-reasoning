"""Folder organization tools. Mutations require a trusted UI approval pin."""
from rat.kernel.registry import Capability, OperationDefinition
from rat.engine.folder_organization import digest
from rat.engine.verification import VerificationReport, VerificationStatus


class OrganizationVerifier:
    def check_execution(self, evidence):
        data = evidence.result
        if not isinstance(data, dict):
            return VerificationReport(VerificationStatus.UNKNOWN, "organization_structure", "Không có kết quả để đối chiếu.", (evidence.id,))
        plan = data.get('plan', data)
        okay = isinstance(plan, dict) and plan.get('digest') == digest(plan)
        if data.get('status') == 'empty':
            okay = True
        if 'entries' in data and data.get('status') != 'empty':
            planned = {(m['name'], m['group'], tuple(m['identity'])) for m in plan.get('moves', [])}
            okay = okay and all((x['name'], x['group'], tuple(x['identity'])) in planned for x in data['entries'])
        return VerificationReport(VerificationStatus.PASS if okay else VerificationStatus.FAIL,
            'organization_structure', 'Đối chiếu kế hoạch và nhật ký; không chứng minh file không bị thay đổi sau đó.',
            (evidence.id,), checked=('plan_digest', 'journal_plan_membership'))

    def check_answer(self, goal, answer, evidence):
        return None


def create_folder_organizer_capability(organizer):
    cap = Capability('folder_organizer', 'Sắp xếp thư mục', 'Xem trước, áp dụng có xác nhận và hoàn tác di chuyển file.')
    move = {'type':'object','required':['name','group','identity'], 'properties': {
        'name':{'type':'string','maxLength':4096}, 'group':{'type':'string','maxLength':64},
        'identity':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'integer'}},
        'state':{'enum':['preview','skipped','moved','move_pending','undone','undo_pending','undo_conflict','identity_conflict','restored_conflict']},
        'reason':{'type':'string','maxLength':4096}}}
    plan_contract = {'type':'object','required':['plan_id','root','root_identity','scope_version','rule','created_at','moves','skipped','scanned','limited','status','digest'],
        'properties':{'plan_id':{'type':'string'}, 'scope_version':{'type':'string'},
            'scanned':{'type':'integer','minimum':0,'maximum':1000},
            'moves':{'type':'array','maxItems':100,'items':move}, 'status':{'enum':['preview']},
            'digest':{'type':'string','maxLength':64}, 'rule':{'enum':['type','month']},
            'root':{'type':'string','maxLength':4096}, 'root_identity':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'integer'}},
            'limited':{'type':'boolean'}, 'skipped':{'type':'object','properties':{key:{'type':'integer','minimum':0} for key in
                ('hidden','folder_or_link','unsafe_destination','name_conflict')}}, 'created_at':{'type':'number'}}}
    receipt_contract = {'type':'object', 'required':['transaction_id','entries','status'],
        'properties':{'transaction_id':{}, 'entries':{'type':'array','maxItems':100,'items':move},
            'status':{'enum':['empty','applying','applied','partial','undone','undo_partial']}, 'plan':plan_contract,
            'created_at':{'type':'number'}, 'finished_at':{'type':'number'}}}
    formatter = lambda data: {'status': data['status'], 'planned_count': len(data.get('moves', [])),
        'entry_states': [x['state'] for x in data.get('entries', [])], 'skipped': data.get('skipped', {})}

    def approved(context, artifact):
        pin = context.get('organization_approval')
        if not context.get('user_initiated') or pin != {'artifact_id': artifact.id, 'revision': artifact.revision}:
            raise ValueError('organization_explicit_approval_required')

    def apply(args, **context):
        artifact = context['target_artifact']
        approved(context, artifact)
        return organizer.apply(artifact.payload, context.get('should_cancel') or (lambda: False))

    def undo(args, **context):
        artifact = context['target_artifact']
        approved(context, artifact)
        return organizer.undo(artifact.payload['transaction_id'], context.get('should_cancel') or (lambda: False))

    cap.register_operation(OperationDefinition('plan_folder_organization',
        'Preview nonrecursive organization by type or modification month inside one allowed folder; never move files.',
        {'type':'object', 'additionalProperties':False, 'properties':{
            'folder':{'type':'string','minLength':1}, 'rule':{'enum':['type','month']}}, 'required':['folder']},
        lambda args, **ctx: organizer.plan(args['folder'], args.get('rule','type'), ctx.get('should_cancel') or (lambda:False)),
        artifact_kind='organization_plan', result_contract=plan_contract, verifier=OrganizationVerifier(), observation_formatter=formatter))
    for name, handler, target in [('apply_folder_organization', apply, 'organization_plan'),
                                  ('undo_folder_organization', undo, 'organization_receipt')]:
        cap.register_operation(OperationDefinition(name, 'Explicit user-approved exclusive file moves; journal every step.',
            {'type':'object','properties':{},'additionalProperties':False}, handler,
            target_kind=target, artifact_kind='organization_receipt', result_contract=receipt_contract,
            verifier=OrganizationVerifier(), observation_formatter=formatter, model_visible=False))
    cap.register_operation(OperationDefinition('get_last_organization', 'Recover the last durable organization receipt without moving files.',
        {'type':'object','properties':{},'additionalProperties':False}, lambda args, **ctx: organizer.latest(),
        artifact_kind='organization_receipt', result_contract=receipt_contract, verifier=OrganizationVerifier(), observation_formatter=formatter,
        model_visible=False))
    return cap
