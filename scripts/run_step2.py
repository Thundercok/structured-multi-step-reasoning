import os
import sys
import mlx_lm
from mlx_lm.sample_utils import make_sampler

REPO = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"

print(f"=== STEP 2: LOAD MODEL {REPO} ===")
model, tokenizer = mlx_lm.load(REPO)
print(f"Model loaded: {REPO}")
print(f"tokenizer.eos_token: {tokenizer.eos_token}")

# Inspect EOS tokens and IDs
eos_ids = getattr(tokenizer, "eos_token_ids", None)
if eos_ids is None:
    # Check tokenizer.eos_token_id
    eid = tokenizer.eos_token_id
    eos_ids = [eid] if isinstance(eid, int) else list(eid)
print(f"eos_token_ids in tokenizer: {eos_ids}")

# Verify <|im_end|>
im_end_id = tokenizer.encode("<|im_end|>")
print(f"token '<|im_end|>' encodes to: {im_end_id}")
assert any(eid in im_end_id or tokenizer.decode([eid]) == "<|im_end|>" for eid in eos_ids) or "<|im_end|>" in tokenizer.eos_token, "Must contain <|im_end|>"

# Run 1 prompt with enable_thinking=False
messages = [{"role": "user", "content": "Nếu 3 quả táo giá 45000 đồng, 7 quả táo giá bao nhiêu?"}]
prompt = tokenizer.apply_chat_template(messages, enable_thinking=False, add_generation_prompt=True)
print("\n=== TEMPLATED PROMPT ===")
print(prompt)

print("=== GENERATING 1 SAMPLE (temp=0.0) ===")
sampler = make_sampler(temp=0.0)
text = ""
finish_reason = None
n_tok = 0
for r in mlx_lm.stream_generate(model, tokenizer, prompt, max_tokens=256, sampler=sampler):
    text += r.text
    n_tok = r.generation_tokens
    if getattr(r, "finish_reason", None) is not None:
        finish_reason = r.finish_reason

print("=== RAW GENERATION OUTPUT ===")
print(text)
print(f"\nfinish_reason: {finish_reason}")
print(f"tokens: {n_tok}")
