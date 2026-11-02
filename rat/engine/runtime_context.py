"""Collect coherent canonical copies for the shared, headless context compiler.

This adapter owns no state. A changed boundary is retried twice, then reported
as a context-build failure rather than feeding mixed revisions to the model.
"""
from __future__ import annotations

import copy
from typing import Any

from rat.engine.completion import TurnContract
from rat.engine.context_snapshot import (
    compile_context_snapshot, validate_context_snapshot, expand_value_refs, find_entity,
)


class ContextBuildError(ValueError):
    pass


def compact_model_context(snapshot):
    """Render useful facts from one validated copy for small native models.

    Full typed snapshots remain available for audits and structured consumers.
    Native tool messages carry the actual current observations; older artifact
    contents can be retrieved by their observed ID/revision with inspect_artifact.
    Empty default contracts and transport metadata are not model instructions.
    """
    result = {}
    indexes = snapshot['indexes']
    for source, target in (('active_notes', 'active_notes'), ('historical_notes', 'historical_notes')):
        notes = []
        for ref in indexes[source]:
            entity = find_entity(snapshot['entities'], ref)
            if entity:
                expanded = expand_value_refs(entity, snapshot)
                notes.append({**expanded['body'], 'authority': entity['authority']})
        if notes:
            result[target] = notes
    if snapshot['proposal']['state']:
        result['proposed_task_state'] = copy.deepcopy(snapshot['proposal']['state'])
    declaration = snapshot['runtime_obligations'].get('contract')
    if declaration and declaration.get('intent_coverage') not in ('unchecked', 'invalid'):
        result['declared_work'] = copy.deepcopy(snapshot['runtime_obligations'])
        result['provisional_progress'] = copy.deepcopy(snapshot['observed_state']['progress'])
    if snapshot['continuity']['turn_refs']:
        result['prior_turns'] = copy.deepcopy(snapshot['continuity']['turn_refs'])
    if snapshot['unmodeled_observations']:
        result['prior_observations'] = copy.deepcopy(snapshot['unmodeled_observations'])
    artifacts = []
    selected = {r['artifact_id'] for r in indexes['selected_results']}
    for ref in indexes['current_results']:
        entity = find_entity(snapshot['entities'], ref)
        if entity:
            body = entity['body']
            artifacts.append({'id': body['id'], 'kind': body['kind'], 'revision': body['revision'],
                              'title': body.get('title', ''), 'inputs': body.get('inputs', {}),
                              'fields': list(body.get('payload', {})),
                              'owner_turn_id': entity.get('owner_turn_id'),
                              'selected': body['id'] in selected})
    if artifacts:
        result['results'] = artifacts
        result['selection_set'] = indexes['selection_set']
    pending = snapshot['observed_state']['lifecycle'].get('pending_input')
    if pending:
        result['pending_input'] = copy.deepcopy(pending)
    effects = [{'operation': r['operation_name'], 'status': r['status'], 'committed': r['committed'],
                'artifact_refs': copy.deepcopy(r['artifact_refs']), 'error': r['error']}
               for r in snapshot['observed_state']['receipts'] if r.get('issuer') == 'dispatcher']
    if effects:
        result['current_effects'] = effects
    if snapshot['unavailable_refs']:
        result['unavailable_refs'] = copy.deepcopy(snapshot['unavailable_refs'])
    return result


def _artifact_refs(value):
    """Collect explicit artifact pins; arbitrary strings are never interpreted."""
    if isinstance(value, dict):
        aid = value.get("artifact_id")
        rev = value.get("artifact_revision", value.get("revision"))
        if isinstance(aid, str) and type(rev) is int and rev > 0:
            yield aid, rev
        for child in value.values():
            yield from _artifact_refs(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _artifact_refs(child)


def collect_runtime_context(*, view, notebook, store, dispatcher, journal,
                            contract, task_state, query, history=None,
                            previous_sources=None, turn_references=None,
                            candidate_hash=None):
    """Compile one validated boundary from canonical copies, without mutation."""
    def boundary():
        ctx = notebook.current_context()
        pending = dispatcher.state.pending_input_request
        return (
            notebook.generation, notebook.event_cursor(),
            ctx.turn_ref.to_dict() if ctx else None,
            ctx.execution_id if ctx else None,
            bool(notebook.selection_set), tuple(notebook.result_ids()),
            store.generation, tuple((a.id, a.revision) for a in store.list()),
            pending.to_dict() if pending else None,
        )

    for _ in range(3):
        before = boundary()
        if (before[0] != journal.generation or before[3] != journal.execution_id
                or not before[2] or before[2]['conversation_id'] != journal.conversation_id
                or before[2]['turn_id'] != journal.turn_id):
            raise ContextBuildError("context_build_failed:execution_changed")
        current = store.list()
        current_refs = [{"kind": "artifact", "conversation_id": journal.conversation_id,
                         "artifact_id": a.id, "revision": a.revision} for a in current]
        notes = notebook.snapshot()
        # Every retained note version is needed for event/replacement closure,
        # including several edits within the same turn.
        historical = []
        for note in notes:
            historical.extend(v for v in notebook.version_history(note["id"])
                              if v["revision"] != note["revision"])
        events = notebook.events_since(0, notebook.conversation_id)
        journal_copy = copy.deepcopy(journal)
        contract_copy = TurnContract.from_dict(contract.to_dict()) if contract is not None else None
        if contract_copy is not None:
            contract_copy.is_valid = contract.is_valid
            contract_copy.validation_errors = list(contract.validation_errors)
            if contract.frozen:
                contract_copy.freeze()
        task_copy = copy.deepcopy(task_state)
        turns = copy.deepcopy((turn_references or [])[-8:])
        by_pin = {(a.id, a.revision): a for a in current}
        unavailable = []
        refs = set(_artifact_refs([notes, historical, events,
                                   journal_copy.to_dict(), turns]))
        for aid, revision in sorted(refs):
            if (aid, revision) in by_pin:
                continue
            art = store.get(aid, revision)
            if art is not None:
                by_pin[(aid, revision)] = art
            else:
                unavailable.append({
                    "ref": {"kind": "artifact", "conversation_id": journal.conversation_id,
                            "artifact_id": aid, "revision": revision},
                    "reason": "revision_no_longer_retained", "mandatory": False,
                })
        after = boundary()
        if before != after:
            continue
        snapshot = compile_context_snapshot(
            view, conversation_id=journal.conversation_id, turn_id=journal.turn_id,
            execution_id=journal.execution_id, generation=journal.generation,
            artifact_store_generation=before[6], note_event_cursor=before[1],
            current_query=query,
            history_message_refs=[f"messages/history/{i}" for i in range(len((history or [])[-12:]))],
            turn_refs=turns, task_state=task_copy, turn_contract=contract_copy,
            execution_journal=journal_copy,
            lifecycle_state={"state": "needs_input" if before[8] else "running",
                             "cancelled": False, "pending_input": before[8]},
            artifact_store_items=list(by_pin.values()), current_artifact_refs=current_refs,
            selected_artifact_ids=list(before[5]), selection_set=before[4],
            notebook_notes=notes, notebook_history=historical, recent_events=events,
            candidate_hash=candidate_hash, unavailable_refs=unavailable,
            # Legacy source metadata has no receipt identity. Preserve it as
            # observed data, never promote it to current execution evidence.
            unmodeled_observations=copy.deepcopy((previous_sources or [])[-8:]),
        )
        valid, errors = validate_context_snapshot(snapshot)
        if not valid:
            raise ContextBuildError("context_build_failed:" + "; ".join(errors))
        if boundary() == before:
            return snapshot
    raise ContextBuildError("context_build_failed:concurrent_change")
