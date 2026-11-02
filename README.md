# Structured-thinking LLM

Fine-tunes Qwen3-8B on Apple Silicon so its thinking follows a structure that code can
check, then tests by intervention whether its answers really depend on that thinking.
Research plan and status: [docs/research_plan.md](docs/research_plan.md).

```text
<think>
Step 1: Natalia sold 48/2 = 24 clips in May.
Calc: 48/2=24
Step 2: Natalia sold 48+24 = 72 clips altogether.
Calc: 48+24=72
</think>

Answer: 72
```

## Layout

| Path | Contents |
| --- | --- |
| `structured_llm/trace.py` | Format: render, parse and deterministic checks |
| `structured_llm/gsm8k.py` | GSM8K conversion and splits |
| `structured_llm/train.sh` | LoRA fine-tune |
| `structured_llm/counterfactual.py` | Deterministic re-execution, counterfactual training data, intervention planning |
| `structured_llm/evaluate.py` | Fine-tuned model vs base-model comparisons on the dev split |
| `structured_llm/intervene.py` | Changes one intermediate result and sees whether the answer follows |
| `structured_llm/pal.py` | Runs model-written programs without `exec` |
| `data/gsm8k_source/` | Pinned GSM8K train file, license and manifest |
| `data/gsm8k_development*/` | Questions already used for development; excluded from the new splits |
| `docs/gsm8k_*.md`, `runs/` | Earlier controller results, kept as reference |

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python -m pytest -q
```

```bash
.venv/bin/python -m structured_llm.gsm8k
```

```bash
structured_llm/train.sh adapters/first 200
```

```bash
.venv/bin/python -m structured_llm.evaluate --adapter adapters/first --limit 20 --out audit/first
```

```bash
.venv/bin/python -m structured_llm.intervene --run audit/first --adapter adapters/first
```

The model must already be in the Hugging Face cache at the pinned revision. Earlier code
(controller, RAT, RAT Lite) is at git tag `pre-rebuild-20261102`.
