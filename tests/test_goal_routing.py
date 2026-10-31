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


def test_clarification_with_short_confirmation_and_analysis_and_file_descriptions():
    from rat.engine.snippet_translation import detect_language

    router = ToolGoalRouter({'find_files', 'translate_text'}, language_detector=detect_language)

    # 1. Trả lời "dịch đi" hoặc "tìm đi" sau khi được hỏi làm rõ sẽ dùng đúng đoạn original
    clarify = router.resolve('Kế hoạch')
    assert clarify.kind == 'needs_input'
    resumed = router.resolve('dịch đi', pending=clarify.input_request)
    assert resumed.operation == 'translate_text'
    assert resumed.args['text'] == 'Kế hoạch'

    resumed_find = router.resolve('tìm đi', pending=clarify.input_request)
    assert resumed_find.operation == 'find_files'
    assert resumed_find.args['query'] == 'Kế hoạch'

    # 2. Câu tìm kiếm tự nhiên: "slide bài giảng chương 3", "hóa đơn tháng 10"
    find1 = router.resolve('slide bài giảng chương 3')
    assert find1.operation == 'find_files'
    assert find1.rule == 'file_description'
    assert find1.args['query'] == 'slide bài giảng chương 3'

    find2 = router.resolve('hóa đơn tháng 10')
    assert find2.operation == 'find_files'
    assert find2.rule == 'file_description'
    assert find2.args['query'] == 'hóa đơn tháng 10'

    # 3. Câu "giải thích ngắn gọn đoạn này" route sang agent (rule='analysis_goal')
    analysis = router.resolve('giải thích ngắn gọn đoạn này')
    assert analysis.kind == 'agent'
    assert analysis.rule == 'analysis_goal'

    # 4. Câu tiếng Việt có dấu câu tự động route sang translate_text (bidirectional_passage)
    vi_sentence = router.resolve('Hôm nay thời tiết thật là đẹp.')
    assert vi_sentence.operation == 'translate_text'
    assert vi_sentence.rule == 'bidirectional_passage'
    assert vi_sentence.args['text'] == 'Hôm nay thời tiết thật là đẹp.'

