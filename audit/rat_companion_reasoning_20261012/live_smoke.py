"""Small exposed-development smoke on fixture data; never a research benchmark."""
from pathlib import Path
from dataclasses import asdict
import json,time,os
from rat.config import config
from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import SLMEngine
from rat.timetable.compositor import TimetableCompositor

out=Path(os.environ.get('RAT_COMPANION_SMOKE_OUTPUT', str(Path(__file__).resolve().parent))); out.mkdir(parents=True,exist_ok=True)
class RecordedClient:
    def __init__(self):
        self.engine=SLMEngine(model=os.environ.get('RAT_COMPANION_SMOKE_MODEL') or config.assistant_model or config.ollama_model)
    def chat_with_meta(self, messages, tools, **kwargs):
        meta=self.engine.chat_with_meta(messages,tools,timeout=float(os.environ.get('RAT_COMPANION_SMOKE_TIMEOUT', '90')),max_tokens=640,**kwargs)
        with (out/'live_calls.jsonl').open('a') as file:
            file.write(json.dumps(meta,ensure_ascii=False)+'\n')
        return meta

client=RecordedClient()
db=Database(str(out/'fixture_index.db'))
runtime=AssistantRuntime(db=db,compositor=TimetableCompositor([]),use_live_model=True,
    model_client=client,plan_tasks=True)
cases=[
    'Ghi lại đúng lời mình cho việc ôn tập: Tôi có 20 phút, chỉ ôn TCP. Lượt này chỉ ghi chú, chưa tìm tài liệu.',
    'Bạn đang ghi điều gì cho việc ôn tập của mình?',
    'Tôi có 30 phút, chỉ ôn TCP. Sửa ghi chú thời gian cũ theo đúng lời này rồi tính 30*60 giúp mình.',
]
history=[]; state={}; rows=[]
for query in cases:
    started=time.perf_counter()
    response=runtime.run(query,max_steps=5,max_tokens=12000,history=history,task_state=state)
    row={'query':query,'response':asdict(response),'notes':runtime.notebook.snapshot(),
         'measured_online_wall_ms':(time.perf_counter()-started)*1000}
    rows.append(row)
    (out/'live_smoke_results.json').write_text(json.dumps({'scope':'exposed_app_development_smoke',
        'model':client.engine.model,'fixture_data_only':True,'research_gate_changed':False,
        'rows':rows},ensure_ascii=False,indent=2))
    print(json.dumps({'query':query,'error':response.error,'answer':response.answer,
        'actions':[step.tool_name for step in response.steps], 'notes':len(row['notes']),
        'tokens':response.total_tokens},ensure_ascii=False),flush=True)
    if response.task_state_updated: state=response.task_state
    history.extend([{'role':'user','content':query},{'role':'assistant','content':response.answer or 'Lượt trước chưa hoàn tất.'}])
db.get_connection().close()
