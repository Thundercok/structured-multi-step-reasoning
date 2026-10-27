"""Bind explicit note instructions to observed artifacts; no model calls or IO.

This recognizes bounded command forms, not general natural-language intent.
Anything outside those forms stays with the existing planner/runtime. Checks
cover requested effects and literal checklist content, not prose correctness.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


NOTE_WRITES = frozenset(('synthesize_smart_note', 'update_note_action_item', 'expand_note_section'))


def normalized(text):
    return ' '.join(str(text).casefold().split()).rstrip('.!?')


class NoteRequirementError(ValueError):
    pass


@dataclass(frozen=True)
class NoteRequirements:
    operation: str = ''
    artifact_id: str | None = None
    revision: int | None = None
    tasks: tuple[str, ...] = ()
    task_match: str = ''
    done: bool | None = None
    heading: str = ''
    error: str | None = None

    def public_data(self):
        return {k: v for k, v in vars(self).items() if v is not None and v != '' and v != ()}

    def outcome(self):
        return {'outcome_id': 'required-note-effect', 'kind': 'registered_effect',
                'effect_type': self.operation,
                'target_ref': ({'artifact_id': self.artifact_id, 'revision': self.revision}
                               if self.artifact_id else None),
                'required_proof_scope': self.operation + '_structure'}

    def check_action(self, name, args, store):
        if name not in NOTE_WRITES or not self.operation:
            return
        if self.error:
            raise NoteRequirementError(self.error)
        if name != self.operation:
            raise NoteRequirementError(f'note_operation_mismatch: required {self.operation}; do not replace it with {name}')
        if not self.artifact_id:
            return
        if args.get('artifact_id') != self.artifact_id or args.get('revision') != self.revision:
            raise NoteRequirementError(f'note_target_mismatch: required {self.artifact_id} revision {self.revision}')
        target = store.get(self.artifact_id)
        if target is None or target.revision != self.revision:
            raise NoteRequirementError('stale_note_target')
        if self.heading and normalized(args.get('section_heading', '')) != normalized(self.heading):
            raise NoteRequirementError(f'note_heading_mismatch: required {self.heading}')
        if self.done is not None:
            if args.get('done', True) is not self.done:
                raise NoteRequirementError(f'note_status_mismatch: required done={self.done}')
            items = target.payload.get('action_items', [])
            index = args.get('item_index')
            match = normalized(args.get('task_match', ''))
            selected = [item for i, item in enumerate(items, 1) if
                        (i == index if index is not None else bool(match) and match in normalized(item.get('task', '')))]
            if len(selected) != 1 or normalized(self.task_match) not in normalized(selected[0].get('task', '')):
                raise NoteRequirementError(f'note_task_mismatch: required task containing {self.task_match}')


def derive_note_requirements(goal, store, turn_ref=None):
    text = goal.strip()
    creation = re.match(r'^(?:hãy\s+)?(?:tạo(?:\s+và\s+lưu)?|lưu)\s+(?:một\s+)?(?:smart\s+note|ghi\s+chú|note)\b', text, re.I)
    toggle = re.search(r'(?:^|[,;]\s*)(?:hãy\s+)?đánh\s+dấu\s+(?:mục\s+)?(.+?)\s+(?:là\s+)?(chưa\s+hoàn\s+thành|đã\s+hoàn\s+thành|hoàn\s+thành|đã\s+xong|xong)\b', text, re.I)
    expansion = re.search(r'(?:^|[,;]\s*)(?:hãy\s+)?(?:bổ\s+sung|mở\s+rộng)\s+(?:mục|phần)\s+([^:\n.!?]+)', text, re.I)
    if creation:
        task = re.search(r'(?:thêm\s+(?:một\s+)?việc\s+cần\s+làm|(?:thêm\s+)?checklist)\s*:\s*(.+?)(?:(?<=[.!?])\s+|\n|$)', text, re.I)
        return NoteRequirements('synthesize_smart_note', tasks=(task[1].strip().rstrip('.!?'),) if task else ())
    if not toggle and not expansion:
        return NoteRequirements()
    # A mutation command must name notes, or be explicitly bound by the UI.
    ref = turn_ref if isinstance(turn_ref, dict) else {
        k: getattr(turn_ref, k, None) for k in ('target_artifact_id', 'target_revision')}
    if not re.search(r'\b(?:note|ghi\s+chú)\b', text, re.I) and not ref.get('target_artifact_id'):
        return NoteRequirements()
    operation = 'update_note_action_item' if toggle else 'expand_note_section'
    notes = store.find_by_kind('structured_note') if store is not None else []
    mentioned = [a for a in notes if re.search(r'(?<![\w-])' + re.escape(a.id) + r'(?![\w-])', text)]
    pinned_id = ref.get('target_artifact_id')
    explicit_ids = re.findall(r'\bart-[\w-]+', text)
    if any(not any(a.id == aid for a in notes) for aid in explicit_ids):
        return NoteRequirements(operation, error='note_target_required')
    if len(mentioned) > 1 or (pinned_id and mentioned and mentioned[0].id != pinned_id):
        return NoteRequirements(operation, error='ambiguous_note_target')
    target = store.get(pinned_id) if pinned_id and store is not None else (mentioned[0] if mentioned else None)
    if target is None and not pinned_id and re.search(r'(?:ghi\s+chú|note)\s+mới\s+nhất\b', text, re.I):
        target = notes[-1] if notes else None
    if target is None or target.kind != 'structured_note':
        return NoteRequirements(operation, error='note_target_required')
    version = re.search(r'\b(?:revision|rev|phiên\s+bản)\s+(\d+)\b', text, re.I)
    revision = ref.get('target_revision') or (int(version[1]) if version else target.revision)
    if version and int(version[1]) != revision:
        return NoteRequirements(operation, error='conflicting_note_revision')
    if revision != target.revision:
        return NoteRequirements(operation, error='stale_note_target')
    return NoteRequirements(operation, target.id, revision,
                            task_match=toggle[1].strip() if toggle else '',
                            done=not toggle[2].casefold().startswith('chưa') if toggle else None,
                            heading=expansion[1].strip() if expansion else '')
