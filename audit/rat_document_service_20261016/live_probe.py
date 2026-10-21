"""Bounded offline development acceptance, nine calls maximum, synthetic files only."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
MODEL = Path.home() / '.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots/32f3e8ecf65426fc3306969496342d504bfa13f3'
state = dict(status='starting', pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
    scope='Headless application acceptance on synthetic development fixtures; not held-out model quality or native UI.',
    max_calls=9, network_attempts=0, model_path=str(MODEL), cases=[])


def save():
    (OUT / 'live_manifest.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))


def audit(event, args):
    if event == 'socket.connect':
        state['network_attempts'] += 1
        raise PermissionError('Native document acceptance is offline')


def deadline():
    state.update(status='timeout', error='240-second process deadline')
    save()
    os._exit(124)


def main():
    sys.addaudithook(audit)
    timer = threading.Timer(240, deadline)
    timer.daemon = True
    timer.start()
    runtime = db = None
    save()
    try:
        import psutil
        if psutil.virtual_memory().available < 3_200_000_000:
            raise RuntimeError('insufficient_available_memory_for_bounded_probe')
        from rat.crawler.db import Database
        from rat.engine.assistant_runtime import AssistantRuntime
        from rat.engine.selected_document_qa import answer_selected_document
        from rat.timetable.compositor import TimetableCompositor

        names = ['rat/engine/document_model_service.py', 'rat/engine/mlx_document_session.py',
                 'rat/engine/selected_document_qa.py', 'rat/engine/assistant_runtime.py',
                 'rat/cli.py', 'rat/main.py', 'tests/test_mlx_document_session.py']
        state['source_hashes'] = {}
        for name in names:
            data = (ROOT / name).read_bytes()
            state['source_hashes'][name] = hashlib.sha256(data).hexdigest()
            dest = OUT / 'source' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        files = OUT / 'fixtures'
        files.mkdir(exist_ok=True)
        a, b, long = [files / name for name in ('workshop-a.txt', 'workshop-b.txt', 'long-notes.txt')]
        a.write_text('TÀI LIỆU MẪU TỔNG HỢP, KHÔNG PHẢI SỰ KIỆN THẬT.\n'
            'Workshop Mây Xanh: mã xác nhận LOTUS-7319. Phòng B203. Bắt đầu lúc 10:30 thứ Năm.\n')
        b.write_text('TÀI LIỆU MẪU TỔNG HỢP. Workshop Suối Đá: mã xác nhận CEDAR-2047. Phòng C105.\n')
        long.write_text('SYNTHETIC DEVELOPMENT FIXTURE. Confirmation code: MAPLE-4826.\n'
                        + 'These are repeated fictional workshop notes for testing excerpt limits.\n' * 70)
        db = Database(str(OUT / 'fixtures.db'))
        for path in (a, b, long):
            db.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext='.txt',
                file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
                content_text=path.read_text()))
        runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), document_model_path=MODEL)
        state['load_s'] = runtime.document_model_client.load()
        import mlx.core as mx
        state['active_after_load_bytes'] = mx.get_active_memory()
        save()

        def ask(name, path, question, expected=None, *, cancel=False, expect_truncated=False):
            assert len(state['cases']) < state['max_calls']
            calls = []
            stopped = threading.Event()
            started = time.perf_counter()
            response = answer_selected_document(runtime, question, str(path), on_model_call=calls.append,
                on_text=(lambda _: stopped.set()) if cancel else None, should_cancel=stopped.is_set)
            wall = time.perf_counter() - started
            meta = calls[0] if calls else {}
            raw = meta.get('raw_response') or {}
            source = next((s for s in response.sources if s.get('path') == str(path) and s.get('read')), {})
            checks = dict(one_call=len(calls) == 1, source_read=bool(source),
                committed_read=any(r.operation_name == 'read_document' and r.committed
                                   for r in response.execution_journal.receipts))
            if cancel:
                checks['cancelled_without_final_answer'] = response.error == 'cancelled' and not response.answer
            else:
                checks['answered_without_error'] = response.error is None
                checks['expected_answer'] = expected.lower() in response.answer.lower()
            if expect_truncated:
                checks['explicit_truncation'] = source.get('truncated') is True and source.get('read_chars', 0) <= 3000
            record = dict(name=name, question=question, file_path=str(path),
                file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), wall_s=wall,
                first_text_s=raw.get('first_text_s'), prefix_prepared=raw.get('prefix_already_prepared'),
                checks=checks, calls=calls, response=asdict(response))
            with (OUT / 'live_calls.jsonl').open('a') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            state['cases'].append({k: record[k] for k in
                ('name', 'wall_s', 'first_text_s', 'prefix_prepared', 'checks')})
            save()
            print(json.dumps(state['cases'][-1]), flush=True)

        ask('first_document_cold', a, 'Mã xác nhận là gì? Chỉ trả lời mã.', 'LOTUS-7319')
        ask('same_document_followup', a, 'Phòng nào? Chỉ trả lời mã phòng.', 'B203')
        ask('switch_document', b, 'Mã xác nhận là gì? Chỉ trả lời mã.', 'CEDAR-2047')
        b.write_text(b.read_text().replace('CEDAR-2047', 'CEDAR-2048'))
        ask('changed_file_same_path', b, 'Mã xác nhận là gì? Chỉ trả lời mã.', 'CEDAR-2048')
        ask('absent_information', b,
            'Email ban tổ chức là gì? Nếu tài liệu không có, trả lời đúng: KHÔNG CÓ TRONG TRÍCH ĐOẠN.',
            'KHÔNG CÓ TRONG TRÍCH ĐOẠN')
        ask('cancel_during_generation', b, 'Viết ba câu mô tả thông tin workshop có trong tài liệu.', cancel=True)
        ask('new_question_after_cancel', b, 'Mã xác nhận? Chỉ trả lời mã.', 'CEDAR-2048')
        ask('long_document_excerpt', long, 'What is the confirmation code? Answer with only the code.',
            'MAPLE-4826', expect_truncated=True)
        runtime.document_model_client.unload()
        state['unloaded'] = not runtime.document_model_client.is_loaded
        ask('reload_after_unload', a, 'Mã xác nhận là gì? Chỉ trả lời mã.', 'LOTUS-7319')
        state['peak_mlx_bytes'] = mx.get_peak_memory()
        state['active_before_close_bytes'] = mx.get_active_memory()
        state['source_changed'] = [name for name, value in state['source_hashes'].items()
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value]
        state['status'] = 'completed' if all(all(c['checks'].values()) for c in state['cases']) else 'failed_checks'
    except Exception as error:
        state.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        print(state['traceback'], flush=True)
    finally:
        if runtime is not None:
            runtime.close()
            state['closed'] = not runtime.document_model_client.is_loaded
        if db is not None:
            db.get_connection().close()
        timer.cancel()
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return 0 if state['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
