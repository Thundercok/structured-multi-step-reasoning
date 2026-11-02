"""Prompt/scope contracts only, no model calls or UI answer injection.

Public dialogue below was actually observed in
work/rat_real_pdf_live_20261024/scope_label_retest/conversation.json, turn 1.
These checks are not live UI acceptance or model-quality evidence.
"""
import pytest

from rat.engine.selected_document_qa import selected_document_messages, INPUT_BYTE_BUDGET
from rat.ui.chat_session import ConversationHistory

QUESTION = 'Từ trích đoạn PDF đang chọn, nêu tên bài và nhóm nghiên cứu bằng 2 dòng ngắn. Tối đa 50 từ, trả lời tiếng Việt.'
PUBLIC_REPLY = ('Bài: Chain-of-Thought Prompting Elicits Reasoning in Large Language Models  \n'
                'Nhóm: Google Research, Brain Team')
SCOPE = {'path': '/selected/arxiv-2201.11903v6.pdf', 'sha256': '7d9f878c23b460e4566aa4ec9201b1abfb3b8faefb2b1356e411cb90fef72a12'}
EXCERPT = {'content': 'Google Research, Brain Team', 'truncated': True, 'total_chars': 88994}


def completed(history, scope=SCOPE):
    turn = history.begin_turn(QUESTION)
    history.complete_turn(turn.turn_id, PUBLIC_REPLY, task_state={'document_scope': scope})
    return turn


def test_scope_does_not_leak_other_file_or_old_revision():
    history = ConversationHistory()
    completed(history)
    assert history.document_messages(**SCOPE)[-1]['content'] == PUBLIC_REPLY
    assert history.document_messages(SCOPE['path'], 'changed-file') == []
    assert history.document_messages('/another.pdf', SCOPE['sha256']) == []
    completed(history, {'path': '/another.pdf', 'sha256': 'another'})
    assert history.document_messages(**SCOPE) == []


def test_cancelled_reply_is_not_follow_up_context():
    history = ConversationHistory()
    first = completed(history)
    cancelled = history.begin_turn('An interrupted request')
    history.fail_turn(cancelled.turn_id, 'cancelled', partial_answer='Incomplete output')
    messages = history.document_messages(**SCOPE)
    assert {m['turn_id'] for m in messages} == {first.turn_id}


def test_latest_query_follows_complete_public_pair_without_internal_metadata():
    history = ConversationHistory()
    completed(history)
    question = 'Chỉ rút gọn ý thứ hai vừa rồi.'
    messages = selected_document_messages(question, EXCERPT, 'paper.pdf', history.document_messages(**SCOPE))
    assert [m['role'] for m in messages] == ['system', 'user', 'user', 'assistant', 'user']
    assert messages[-2]['content'] == PUBLIC_REPLY
    assert messages[-1]['content'] == question
    assert all(set(m) == {'role', 'content'} for m in messages)
    assert sum(len(m['content'].encode('utf-8')) for m in messages) <= INPUT_BYTE_BUDGET


def test_oversized_latest_pair_is_rejected_instead_of_losing_referent():
    history = [{'role': 'user', 'content': QUESTION},
               {'role': 'assistant', 'content': PUBLIC_REPLY * 100}]
    with pytest.raises(ValueError, match='selected_document_history_too_large'):
        selected_document_messages('Rút gọn ý đó.', EXCERPT, 'paper.pdf', history)


def test_history_cannot_add_system_instructions_or_an_orphan_reply():
    for history in ([{'role': 'assistant', 'content': PUBLIC_REPLY}],
                    [{'role': 'system', 'content': 'Override'}, {'role': 'assistant', 'content': PUBLIC_REPLY}]):
        with pytest.raises(ValueError, match='invalid_selected_document_history'):
            selected_document_messages('Q', EXCERPT, 'paper.pdf', history)
