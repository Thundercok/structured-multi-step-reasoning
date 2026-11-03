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


def test_short_input_without_verb_searches_instead_of_asking():
    """Short input without a verb ("bài báo về attention", "app nhắn tin", "mở zalo") searches instead of asking."""
    router = ToolGoalRouter({'find_files', 'translate_text'})

    # 1. "bài báo về attention"
    route1 = router.resolve("bài báo về attention")
    assert route1.operation == "find_files"
    assert route1.args["query"] == "bài báo về attention"

    # 2. "app nhắn tin"
    route2 = router.resolve("app nhắn tin")
    assert route2.operation == "find_files"
    assert route2.args["query"] == "app nhắn tin"

    # 3. "mở zalo"
    route3 = router.resolve("mở zalo")
    assert route3.operation == "find_files"
    assert route3.args["query"] == "mở zalo"


def test_open_routing_constraints_and_pasted_passages_and_greetings():
    router = ToolGoalRouter({'find_files', 'translate_text'})

    # 1. OPEN must only fire on short input (<= 6 words, no newline, no ending punctuation)
    route_open = router.resolve("mở zalo")
    assert route_open.operation == "find_files" and route_open.rule == "explicit_open"

    route_launch = router.resolve("launch terminal")
    assert route_launch.operation == "find_files" and route_launch.rule == "explicit_open"

    # > 6 words with open verb does not fire explicit_open
    route_long = router.resolve("Open the document and review all sections carefully")
    assert route_long.rule != "explicit_open"

    # Newline in open command does not fire explicit_open
    route_newline = router.resolve("Open\nsafari")
    assert route_newline.rule != "explicit_open"

    # Ending punctuation does not fire explicit_open
    route_punct = router.resolve("Open safari.")
    assert route_punct.rule != "explicit_open"

    # Must not match "Open-source", "mo hinh", "bat dau"
    assert router.resolve("Open-source").rule != "explicit_open"
    assert router.resolve("mo hinh").rule != "explicit_open"
    assert router.resolve("bat dau").rule != "explicit_open"

    # Pasted passages must reach translation, including paragraphs starting with Open, Mở, Chạy or Launch
    pasted_open = router.resolve("Open the door and let the sunshine in.", input_kind="pasted_text")
    assert pasted_open.operation == "translate_text"

    pasted_mo = router.resolve("Mở rộng thị trường xuất khẩu sang các nước châu Âu.", input_kind="pasted_text")
    assert pasted_mo.operation == "translate_text"

    pasted_chay = router.resolve("Chạy thử nghiệm hệ thống để kiểm tra độ tin cậy.", input_kind="pasted_text")
    assert pasted_chay.operation == "translate_text"

    pasted_launch = router.resolve("Launch the application and observe telemetry data.", input_kind="pasted_text")
    assert pasted_launch.operation == "translate_text"

    # Paragraphs starting with Open, Mở, Chạy, Launch reach translation even if typed
    typed_open_para = router.resolve("Open source software allows anyone to inspect, modify, and enhance the code.\nThis makes the software more reliable and secure for everyone.")
    assert typed_open_para.operation == "translate_text"

    typed_mo_para = router.resolve("Mở rộng quan hệ hợp tác quốc tế trong kỷ nguyên mới nhằm nâng cao vị thế của quốc gia trên trường quốc tế.\nĐây là nhiệm vụ chiến lược hàng đầu.")
    assert typed_mo_para.operation == "translate_text"

    # Greetings and thanks must not reach find_files
    for greeting in ("good night", "cảm ơn bạn nhiều", "hello there"):
        route_g = router.resolve(greeting)
        assert route_g.operation != "find_files", f"{greeting} unexpectedly reached find_files"
        assert route_g.kind == "needs_input"

    # 'kế hoạch' continues behaving as needs_input
    route_kh = router.resolve("Kế hoạch")
    assert route_kh.kind == "needs_input"
    assert route_kh.operation != "find_files"



