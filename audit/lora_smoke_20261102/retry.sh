#!/bin/zsh
PY=/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/.venv/bin/python
export HF_HUB_OFFLINE=1 MLX_MAX_OPS_PER_BUFFER=10 MLX_MAX_MB_PER_BUFFER=512
cd "$(dirname "$0")"
echo "=== load before"; memory_pressure | tail -1; uptime
echo "=== 8B retry: batch 1, 12 iters"
/usr/bin/time -l $PY -m mlx_lm lora --model mlx-community/Qwen3-8B-4bit --train --data data --fine-tune-type lora --num-layers 8 --batch-size 1 --iters 12 --learning-rate 1e-5 --max-seq-length 512 --grad-checkpoint --steps-per-report 4 --steps-per-eval 1000 --val-batches 1 --save-every 1000 --adapter-path adapters_8b_retry --seed 0 2>&1 | tr '\r' '\n' | grep -E 'Iter |Trainable|Error|error|real|peak memory|Saved'
echo "=== 4B adapter load and generate"
$PY - <<'PY'
import time
from mlx_lm import load, generate
m,t=load('mlx-community/Qwen3.5-4B-MLX-4bit',adapter_path='adapters_4b')
p=t.apply_chat_template([{"role":"user","content":"Lan has 12 pens and buys 5 more. How many pens does she have?"}],add_generation_prompt=True,tokenize=False,enable_thinking=False)
s=time.time(); o=generate(m,t,prompt=p,max_tokens=60,verbose=False); e=time.time()-s
print('seconds',round(e,1)); print(repr(o[:300]))
PY
echo DONE
