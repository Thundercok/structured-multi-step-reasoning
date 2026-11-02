"""Collect the two tails from one proposed lookup, without invented quality labels."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from rat.engine.assistant_runtime import AgentStep, ModelDecision
from rat.engine.controller import AgentStateTracker, state_features


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()


def collect_pair(runtime, goal, *, proposal_tool='read_document', max_steps=8, **context):
    if runtime.controller is not None:
        raise ValueError('Paired collection needs the uncontrolled runtime')
    if proposal_tool not in {'get_schedule', 'search_documents', 'read_document'}:
        raise ValueError('Pair a supported lookup action')
    common = runtime.run(goal, max_steps=max_steps, stop_before_tool=lambda name, args, steps: name == proposal_tool, **context)
    if common.error != 'checkpoint_reached':
        return {'status': 'checkpoint_not_reached', 'common': asdict(common), 'pair': None}
    prefix, proposal = common.steps[:-1], common.steps[-1]
    raw = json.loads(proposal.raw_completion) if proposal.raw_completion else {}
    if len(raw.get('tool_calls', [])) > 1:
        return {'status': 'parallel_proposal_unsupported', 'common': asdict(common), 'pair': None}
    # Common context uses the latest model-authored task state, not a reconstruction
    # from tool presence. Tools may have populated it before the checkpoint.
    branch_context = {**context, 'task_state': common.task_state}
    stopped = deepcopy(proposal)
    stopped.error = None
    stopped.tool_result = {'error': 'paired_stop', 'detail': 'Counterfactual stop: proposed lookup was not executed. Synthesize using prior observations.'}
    # A no-tools synthesis is supplied as an initial model decision so it is one
    # real recorded call, not an extra decision disguised as a zero-cost answer.
    stop_decision = runtime._call_model(goal, prefix + [stopped], **branch_context, finish_only=True)
    stop = runtime.run(goal, max_steps=1, initial_steps=prefix + [stopped],
                       initial_decision=stop_decision, **branch_context)
    # Selection was already measured once at the common state. Attribute that
    # same call to each path; collection overhead counts it only once.
    stop.prompt_tokens += proposal.prompt_tokens
    stop.completion_tokens += proposal.completion_tokens
    stop.total_tokens = stop.token_estimate = stop.prompt_tokens + stop.completion_tokens
    stop.model_time_ms += proposal.model_duration_ms
    stop.total_time_ms += proposal.model_duration_ms + stop_decision.model_duration_ms
    decision = ModelDecision('', tool_name=proposal.tool_name, tool_args=deepcopy(proposal.tool_args),
        raw_completion=proposal.raw_completion, model_input=proposal.model_input,
        prompt_tokens=proposal.prompt_tokens, completion_tokens=proposal.completion_tokens,
        model_duration_ms=proposal.model_duration_ms)
    continued = runtime.run(goal, max_steps=max_steps, initial_steps=prefix, initial_decision=decision, **branch_context)
    continued.total_time_ms += proposal.model_duration_ms
    tracker = AgentStateTracker()
    for step in prefix:
        if step.tool_name:
            tracker.update_with_tool_result(step.tool_name, step.tool_args, step.tool_result)
    tracker.step_number = proposal.step_number
    tracker.total_tokens = common.total_tokens
    pair = {'goal': goal, 'context': {k: v.isoformat() if hasattr(v, 'isoformat') else v for k, v in context.items()},
            'prefix': [asdict(s) for s in prefix], 'proposal': asdict(proposal),
            'features': state_features(tracker, proposal.tool_name, proposal.tool_args),
            'stop': asdict(stop), 'continue': asdict(continued),
            'token_scope': 'shared_proposal_selection_plus_all_branch_prompt_and_completion',
            'common_prefix_tokens': common.total_tokens - proposal.prompt_tokens - proposal.completion_tokens,
            'collection_tokens': common.total_tokens + stop.total_tokens + continued.total_tokens - 2 * (proposal.prompt_tokens + proposal.completion_tokens),
            'quality_gain': None, 'review_status': 'pending',
            'latency_scope': 'measured_branch_tail_plus_shared_selection; sequential counterfactual collection, not deployed-policy latency'}
    return {'status': 'paired', 'common': asdict(common), 'pair': pair,
            'pair_trace_sha256': hashlib.sha256(canonical_bytes(pair)).hexdigest()}
