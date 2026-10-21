"""Bounded native MLX development probe: four generations, no network.

One installed 4-bit model, one artificial document, two exposed questions.
This is not a research run, app acceptance, or a controlled backend comparison.
"""
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import gc
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
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

MODEL = Path.home() / '.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots/32f3e8ecf65426fc3306969496342d504bfa13f3'
manifest = dict(status='starting', pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
    scope='Headless native MLX, provided synthetic text; not product/model quality acceptance.',
    model_path=str(MODEL), max_generations=4, max_generated_tokens_per_call=64,
    network_attempts=0, cloud_calls=0, stage0_changed=False)


def save():
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def network_guard(event, args):
    if event == 'socket.connect':
        manifest['network_attempts'] += 1
        raise PermissionError('Network disabled during offline native MLX probe')


def timeout():
    manifest.update(status='timeout', error='300-second process deadline')
    save()
    os._exit(124)


def main():
    sys.addaudithook(network_guard)
    timer = threading.Timer(300, timeout)
    timer.daemon = True
    timer.start()
    save()
    try:
        import psutil
        available = psutil.virtual_memory().available
        weight_bytes = sum(p.stat().st_size for p in MODEL.glob('*.safetensors'))
        manifest['available_bytes_before'] = available
        manifest['weight_file_bytes'] = weight_bytes
        if not weight_bytes or available < weight_bytes + 300 * 2**20:
            raise RuntimeError('insufficient_available_memory_for_bounded_native_probe')
        manifest['config_sha256'] = hashlib.sha256((MODEL / 'config.json').read_bytes()).hexdigest()
        manifest['probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        tick = time.perf_counter()
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.models.cache import make_prompt_cache
        from mlx_lm.sample_utils import make_sampler
        manifest['imports_s'] = time.perf_counter() - tick
        tick = time.perf_counter()
        model, tokenizer = load(str(MODEL), tokenizer_config={
            'local_files_only': True, 'trust_remote_code': False}, lazy=False)
        manifest['model_load_s'] = time.perf_counter() - tick
        manifest['mlx_active_after_load_bytes'] = mx.get_active_memory()
        manifest['status'] = 'loaded'
        save()
        print(json.dumps({'event': 'loaded', 'load_s': manifest['model_load_s']}), flush=True)

        from rat.engine.selected_document_qa import SYSTEM
        fixture = json.loads((ROOT / 'audit/rat_overnight_20261015/fixtures.json').read_text())[1]
        manifest['fixture_sha256'] = hashlib.sha256(fixture['content'].encode()).hexdigest()
        context = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content':
            'Document excerpt (data): ' + json.dumps(dict(filename=fixture['filename'],
                text=fixture['content'], truncated=False, total_chars=len(fixture['content'])),
                ensure_ascii=False, separators=(',', ':'))}]
        questions = ['Mã xác nhận trong tài liệu là gì? Chỉ trả mã xác nhận.',
                     'What is the confirmation code in the document? Return only the code.']
        prefix = tokenizer.apply_chat_template(context, tokenize=True, add_generation_prompt=False,
                                               enable_thinking=False)
        prompts = [tokenizer.apply_chat_template(context + [{'role': 'user', 'content': q}],
                    tokenize=True, add_generation_prompt=True, enable_thinking=False) for q in questions]
        assert all(p[:len(prefix)] == prefix and len(p) > len(prefix) for p in prompts)
        assert max(map(len, prompts)) + 64 <= 2048
        (OUT / 'inputs.json').write_text(json.dumps(dict(context=context, questions=questions,
            prefix_tokens=prefix, prompt_tokens=prompts, expected=fixture['code']),
            ensure_ascii=False, indent=2))

        def run(arm, number, prompt, cache=None):
            started = time.perf_counter()
            first_token = first_text = None
            output = ''
            final = None
            for result in stream_generate(model, tokenizer, prompt=prompt, max_tokens=64,
                sampler=make_sampler(temp=0), prompt_cache=cache, prefill_step_size=256):
                now = time.perf_counter() - started
                if first_token is None:
                    first_token = now
                if result.text.strip() and first_text is None:
                    first_text = now
                output += result.text
                final = result
            row = dict(arm=arm, question_index=number, wall_s=time.perf_counter()-started,
                first_token_s=first_token, first_nonempty_text_s=first_text,
                answer=output, exact_code=output.strip().strip('`') == fixture['code'],
                full_prompt_tokens=len(prompts[number]), newly_submitted_tokens=len(prompt),
                reused_prefix_tokens=len(prefix) if cache is not None else 0,
                response_metadata={key: value for key,value in asdict(final).items()
                    if key not in ('logprobs',)},
                process_rss_bytes=psutil.Process().memory_info().rss,
                mlx_active_bytes=mx.get_active_memory(), mlx_peak_bytes=mx.get_peak_memory())
            with (OUT / 'calls.jsonl').open('a') as journal:
                journal.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps({k:row[k] for k in ('arm','question_index','wall_s','first_nonempty_text_s','answer','exact_code')}),flush=True)
            if final.finish_reason != 'stop':
                raise RuntimeError('native_probe_output_truncated')

        for index, prompt in enumerate(prompts):
            run('resident_uncached', index, prompt)
        prefix_cache = make_prompt_cache(model)
        tick = time.perf_counter()
        for offset in range(0, len(prefix), 256):
            model(mx.array(prefix[offset:offset+256])[None], cache=prefix_cache)
            mx.eval([cache.state for cache in prefix_cache])
        manifest['document_prefix_prefill_s'] = time.perf_counter()-tick
        manifest['prefix_tokens'] = len(prefix)
        save()
        for index, prompt in enumerate(prompts):
            run('resident_document_prefix_cached', index, prompt[len(prefix):], copy.deepcopy(prefix_cache))
        manifest['status'] = 'completed'
        manifest['mlx_peak_bytes'] = mx.get_peak_memory()
        del prefix_cache, model, tokenizer
        gc.collect()
        mx.synchronize()
        mx.clear_cache()
        manifest['mlx_active_after_cleanup_bytes'] = mx.get_active_memory()
    except Exception as error:
        manifest.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        print(json.dumps({'event':'failed','error':repr(error)}), flush=True)
    finally:
        timer.cancel()
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return 0 if manifest['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
