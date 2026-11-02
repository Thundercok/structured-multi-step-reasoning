"""Shared local readiness observation, also projected by the Hello screen."""
from rat.kernel.registry import Capability, OperationDefinition
from rat.engine.mini_readiness import check_readiness


def create_mini_setup_capability(settings):
    cap = Capability('mini_setup', 'Thiết lập', 'Quan sát cục bộ các thành phần cần thiết.')
    def check(args, **ctx):
        if args.get('deep') and not ctx.get('user_initiated'):
            raise ValueError('readiness_check_requires_user_action')
        return check_readiness(settings, deep=args.get('deep', False), cancel=ctx.get('should_cancel') or (lambda:False))
    cap.register_operation(OperationDefinition('check_mini_readiness', 'Inspect local setup without requesting permissions or sending data.',
        {'type':'object','additionalProperties':False,'properties':{'deep':{'type':'boolean'}}}, check,
        artifact_kind='mini_readiness', result_contract={'type':'object','required':['status','checks','checked_at','deep'], 'properties': {
            'status':{'enum':['ready','needs_attention']}, 'checked_at':{'type':'number'}, 'deep':{'type':'boolean'},
            'checks':{'type':'array','maxItems':20,'items':{'type':'object','required':['key','label','state','detail'],
                'properties':{'key':{'type':'string'}, 'label':{'type':'string'}, 'detail':{'type':'string'},
                    'state':{'enum':['ready','action_required','unverified','not_required']}}}}}},
        model_visible=False))
    return cap
