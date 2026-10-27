"""Small ingress checks; no model/backend or live UI acceptance claim."""
from rat.engine.goal_routing import ToolGoalRouter
from rat.kernel.contracts import InputRequest


def test_intent_and_clarification_preserve_original_text():
    router = ToolGoalRouter({'find_files','translate_text'})
    question = router.resolve('Hello world')
    assert question.kind == 'needs_input'
    answer = router.resolve('dịch', pending=question.input_request)
    assert answer.operation == 'translate_text'
    assert answer.args['text'] == 'Hello world'
    missing = router.resolve('dịch sang tiếng Anh')
    resumed = router.resolve('Xin chào', pending=missing.input_request)
    assert resumed.args == {'text':'Xin chào','source_language':'auto','target_language':'en'}


def test_explicit_new_task_supersedes_question_and_tools_stay_scoped():
    router = ToolGoalRouter({'find_files','translate_text'})
    pending = router.resolve('dịch').input_request
    new = router.resolve('tìm báo cáo hôm qua',pending=pending)
    assert new.operation == 'find_files' and new.args['query'] == 'báo cáo hôm qua'
    assert router.resolve('test.pdf').operation == 'find_files'
    assert router.resolve('dịch đoạn này').kind == 'needs_input'
    assert ToolGoalRouter({'find_files'}).resolve('dịch: Hello').kind == 'needs_input'


def test_tool_input_continuation_keeps_source_binding():
    router = ToolGoalRouter({'translate_text'})
    pending = InputRequest('translate_text',supplied_inputs={'source_ref':{'artifact_id':'capture-1','revision':1},'target_language':'vi'},missing_fields=[{'name':'source_language'}])
    route = router.resolve('English',tool_input=pending)
    assert route.args['source_language'] == 'en'
    assert route.args['source_ref'] == pending.supplied_inputs['source_ref']
