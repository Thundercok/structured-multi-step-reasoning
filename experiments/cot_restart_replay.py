"""Token-preserving, headless cap replay; no model imports or generation.

Only EOS-stopped, cap-independent single draws are supported. Text-only legacy
artifacts are deliberately rejected: retokenization cannot recover original IDs.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable


TOKEN_RECORD_VERSION = 1
CAP_SWEEP_SEED_POLICY = "item-arm-call-v1"


def derive_cap_sweep_seed(base_seed: int, item: str, arm: str, call: int = 0) -> int:
    """One draw shared across replayed caps; budget is intentionally absent."""
    value = f"{CAP_SWEEP_SEED_POLICY}:{base_seed}:{item}:{arm}:{call}"
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "big")


def encode_prompt(tokenizer: Any, prompt: str) -> list[int]:
    """Match MLX-LM's string-prompt BOS rule, then pass explicit IDs to it."""
    bos = getattr(tokenizer, "bos_token", None)
    add_special_tokens = bos is None or not prompt.startswith(bos)
    return list(tokenizer.encode(prompt, add_special_tokens=add_special_tokens))


def decoding_config(temp: float, top_p: float, *, is_thinking: bool = False) -> dict:
    """Fixed defaults passed explicitly, independent of completion cap."""
    return {
        "temperature": temp,
        "top_p": top_p,
        "max_kv_size": None,
        "prompt_cache": None,
        "logits_processors": None,
        "prefill_step_size": 2048,
        "kv_bits": None,
        "kv_group_size": 64,
        "quantized_kv_start": 0,
        "draft_model": None,
        "stop_strings": [],
        "is_thinking": is_thinking,
        "cap_only_stopping": True,
    }


def backend_kwargs(config: dict) -> dict:
    return {key: config[key] for key in (
        "max_kv_size", "prompt_cache", "logits_processors", "prefill_step_size",
        "kv_bits", "kv_group_size", "quantized_kv_start", "draft_model",
    )}


def backend_runtime_identity(*, mock: bool) -> dict:
    """Record installed versions/source without importing MLX or model weights."""
    if mock:
        return {
            "backend_version": "causal-mock-v1",
            "backend_generate_sha256": None,
            "tokenizer_version": {"implementation": "mock-four-character-v1"},
        }
    versions = {}
    for name in ("mlx-lm", "mlx", "transformers", "tokenizers"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    source_hash = None
    if versions["mlx-lm"] is not None:
        source = Path(metadata.distribution("mlx-lm").locate_file("mlx_lm/generate.py"))
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "backend_version": versions["mlx-lm"],
        "backend_package_versions": versions,
        "backend_generate_sha256": source_hash,
        "tokenizer_version": {k: versions[k] for k in ("transformers", "tokenizers")},
    }


def runtime_metadata(tokenizer: Any, *, mock: bool) -> dict:
    result = backend_runtime_identity(mock=mock)
    result.update({
        "tokenizer_class": type(tokenizer).__name__,
        "tokenizer_name_or_path": str(getattr(tokenizer, "name_or_path", "unknown")),
    })
    directory = Path(result["tokenizer_name_or_path"])
    result["tokenizer_assets_sha256"] = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ("tokenizer.json", "tokenizer_config.json")
        if directory.is_dir() and (directory / name).is_file()
    }
    return result


def collect_token_stream(
    events: Iterable[Any], tokenizer: Any, *, prompt_ids: list[int],
    cap: int, seed: int, config: dict, mock: bool,
) -> dict:
    """Capture every sampled ID, including the terminal EOS event from MLX."""
    if type(cap) is not int or cap < 1:
        raise ValueError("completion cap must be a positive integer")
    ids, text, finish = [], "", None
    for event in events:
        if finish is not None:
            raise ValueError("backend yielded tokens after its finish event")
        ids.append(int(event.token))
        if event.generation_tokens != len(ids):
            raise ValueError("backend token count does not match captured IDs")
        if event.prompt_tokens != len(prompt_ids):
            raise ValueError("backend prompt count does not match prompt IDs")
        text += event.text
        finish = event.finish_reason
    eos = sorted(int(t) for t in tokenizer.eos_token_ids)
    has_eos = bool(ids and ids[-1] in eos)
    if not ids or len(ids) > cap or any(t in eos for t in ids[:-1]):
        raise ValueError("invalid completion IDs or completion exceeds cap")
    if finish not in ("stop", "length") or (finish == "stop") != has_eos:
        raise ValueError("unsupported finish event: this contract stops only on EOS")
    if finish == "length" and len(ids) != cap:
        raise ValueError("length finish before completion cap")
    result = {
        "token_record_version": TOKEN_RECORD_VERSION,
        "prompt_token_ids": list(prompt_ids),
        "completion_token_ids": ids,
        "prompt_tokens": len(prompt_ids),
        "completion_tokens": len(ids),
        "completion_cap": cap,
        "completion_token_scope": "sampled_tokens_including_terminal_eos",
        "eos_token_ids": eos,
        "includes_eos": has_eos,
        "finished": has_eos,
        "finish_reason": finish,
        "raw_output": text,
        "seed": seed,
        "decoding_config": config,
        "text_decoder": "tokenizer_decode" if mock else "mlx_streaming_detokenizer",
        **runtime_metadata(tokenizer, mock=mock),
    }
    return result


def decode_completion(ids: list[int], tokenizer: Any, mode: str) -> str:
    """Finalize at the cut, using the same renderer as the collected call."""
    if mode == "tokenizer_decode":
        return tokenizer.decode(ids)
    if mode != "mlx_streaming_detokenizer":
        raise ValueError("unsupported text decoder")
    decoder = tokenizer.detokenizer
    text = ""
    for index, token in enumerate(ids):
        decoder.add_token(token)
        if index < len(ids) - 1:
            text += decoder.last_segment
    decoder.finalize()
    return text + decoder.last_segment


def replay_completion(record: dict, tokenizer: Any, cap: int, *, prefix_text: str = "") -> dict:
    """Replay a lower cap; neither inspect the tail for answers nor reuse scoring."""
    if record.get("token_record_version") != TOKEN_RECORD_VERSION:
        raise ValueError("exact replay requires original token IDs; text-only record rejected")
    if type(cap) is not int or not 0 <= cap <= record["completion_cap"]:
        raise ValueError("replay cap must be between zero and the collected cap")
    config = record["decoding_config"]
    if not config.get("cap_only_stopping") or config.get("stop_strings"):
        raise ValueError("unsupported stopping/decoding contract; replay refused")
    ids = record["completion_token_ids"]
    current_metadata = runtime_metadata(tokenizer, mock=record["backend_version"] == "causal-mock-v1")
    for field in ("tokenizer_class", "tokenizer_version", "tokenizer_assets_sha256",
                  "backend_version", "backend_generate_sha256"):
        if record.get(field) != current_metadata[field]:
            raise ValueError(f"replay runtime/tokenizer mismatch: {field}")
    if record.get("backend_package_versions") != current_metadata.get("backend_package_versions"):
        raise ValueError("replay runtime/tokenizer mismatch: backend_package_versions")
    eos = set(record["eos_token_ids"])
    if eos != set(tokenizer.eos_token_ids):
        raise ValueError("replay tokenizer EOS IDs differ from the collected tokenizer")
    if (len(ids) != record["completion_tokens"] or len(ids) > record["completion_cap"]
            or len(record["prompt_token_ids"]) != record["prompt_tokens"]
            or any(t in eos for t in ids[:-1])):
        raise ValueError("inconsistent recorded token IDs/counts")
    ended = bool(ids and ids[-1] in eos)
    if (record.get("includes_eos") != ended or record.get("finished") != ended
            or record["completion_token_scope"] != "sampled_tokens_including_terminal_eos"):
        raise ValueError("recorded finish/token scope does not match EOS")
    if record["finish_reason"] != ("stop" if ended else "length"):
        raise ValueError("recorded finish flag does not match EOS")
    if not ended and len(ids) != record["completion_cap"]:
        raise ValueError("incomplete length-stopped record")
    original_visible = ids[:-1] if ended else ids
    if decode_completion(original_visible, tokenizer, record["text_decoder"]) != record["raw_output"]:
        raise ValueError("original token IDs do not reproduce recorded text")
    cut = ids[:cap]
    finished = bool(cut and cut[-1] in eos)
    visible = cut[:-1] if finished else cut
    text = decode_completion(visible, tokenizer, record["text_decoder"])
    return {
        "raw_output": text,
        "full_response": prefix_text + text,
        "completion_token_ids": cut,
        "completion_tokens": len(cut),
        "completion_token_scope": record["completion_token_scope"],
        "includes_eos": finished,
        "finished": finished,
        "finish_reason": "stop" if finished else "length",
        "replay_cap": cap,
        "evidence": "synthetic_mock_replay" if record["backend_version"] == "causal-mock-v1"
                    else "development_token_replay",
    }


def score_replay(record: dict, tokenizer: Any, cap: int, item: dict, *, prefix_text: str = "") -> dict:
    """Use the existing typed parser/checker on only the retained response."""
    from reasoning_strategies import parse_answer_details
    from scripts.gen_tasks import check

    result = replay_completion(record, tokenizer, cap, prefix_text=prefix_text)
    response = result["full_response"]
    if record["decoding_config"].get("is_thinking"):
        if "</think>" not in response:
            return {**result, "parsed_answer": None, "parse_status": "truncated_thinking",
                    "wordy": False, "correct": False}
        response = response.split("</think>")[-1]
    answer_type = {"arith": "number", "order": "text", "g24": "expression"}[item["family"]]
    parsed, status, wordy = parse_answer_details(response, answer_type=answer_type)
    return {**result, "parsed_answer": parsed, "parse_status": status, "wordy": wordy,
            "correct": bool(check(item, parsed)) if parsed is not None else False}
