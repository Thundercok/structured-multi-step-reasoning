"""Acceptance checks T1-T4 with causal mocks only; no model imports/calls."""

import copy
import json
import random
import sys
from types import ModuleType, SimpleNamespace

import pytest

from experiments.cot_restart_addendum import DEFAULT_HISTORICAL_DIR, run_cot_restart_addendum
from experiments.cot_restart_pilot import MockLLM, execute_llm_call
from experiments.cot_restart_replay import (
    CAP_SWEEP_SEED_POLICY, derive_cap_sweep_seed, replay_completion, score_replay,
)
from reasoning.reasoning_strategies import parse_answer_details
from scripts.audit_cot_restart_tokens import audit_rows


def collect(model, prompt, cap, seed=42, thinking=False):
    record = {}
    text, tokens, finish, _ = execute_llm_call(
        model, model.tokenizer, prompt, cap, .6, seed,
        is_mock=True, is_thinking=thinking, capture=record,
    )
    assert (text, tokens, finish) == (
        record["raw_output"], record["completion_tokens"], record["finish_reason"],
    )
    return record


def test_t1_backend_spy_changes_only_max_tokens(monkeypatch):
    import experiments.cot_restart_replay as replay_module

    model = MockLLM(eos_at=13)
    calls, seeds, samplers = [], [], []
    mlx, core, lm, sample = (ModuleType(n) for n in (
        "mlx", "mlx.core", "mlx_lm", "mlx_lm.sample_utils",
    ))
    core.random = SimpleNamespace(seed=seeds.append)
    mlx.core = core

    def make_sampler(**kwargs):
        samplers.append(kwargs)
        return tuple(sorted(kwargs.items()))

    def spy(model_arg, tokenizer, prompt_ids, **kwargs):
        assert model_arg is model and tokenizer is model.tokenizer
        calls.append({"prompt_ids": list(prompt_ids), **kwargs})
        return model.stream_events(prompt_ids, max_tokens=kwargs["max_tokens"], seed=42,
                                   config={"temperature": .6, "is_thinking": False})

    sample.make_sampler, lm.stream_generate = make_sampler, spy
    for name, module in (("mlx", mlx), ("mlx.core", core), ("mlx_lm", lm),
                         ("mlx_lm.sample_utils", sample)):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(replay_module, "runtime_metadata", lambda *a, **kw: {
        "backend_version": "spy", "tokenizer_class": "MockTokenizer",
    })
    records = []
    for cap in (10, 20):
        record = {}
        execute_llm_call(model, model.tokenizer, "Cùng prompt 42", cap, .6, 42, capture=record)
        records.append(record)
    assert seeds == [42, 42]
    assert samplers[0] == samplers[1] == {"temp": .6, "top_p": .95}
    assert calls[0].pop("max_tokens") == 10
    assert calls[1].pop("max_tokens") == 20
    assert calls[0] == calls[1]
    assert calls[0]["prompt_cache"] is None
    assert calls[0]["max_kv_size"] is None
    assert calls[0]["logits_processors"] is None
    assert records[0]["prompt_token_ids"] == records[1]["prompt_token_ids"]
    assert records[0]["decoding_config"] == records[1]["decoding_config"]


@pytest.mark.parametrize("eos_at,finished", [(9, True), (10, True), (11, False)])
def test_t2_eos_at_l_minus_one_l_and_l_plus_one(eos_at, finished):
    model = MockLLM(eos_at=eos_at)
    short, long = collect(model, "prompt", 10), collect(model, "prompt", 20)
    replay = replay_completion(long, model.tokenizer, 10)
    assert short["completion_token_ids"] == long["completion_token_ids"][:10]
    assert replay["raw_output"] == short["raw_output"]
    assert replay["finished"] == short["finished"] == finished
    assert replay["finish_reason"] == ("stop" if finished else "length")
    assert short["includes_eos"] == finished
    assert short["completion_tokens"] == min(10, eos_at)


def test_t3_thousand_random_draws_replay_matches_direct_generation_and_parser():
    rng = random.Random(20261013)
    parsed_successes = finished_cases = length_cases = 0
    for _ in range(1200):
        high = rng.randrange(2, 60)
        low = rng.randrange(1, high + 1)
        model = MockLLM(eos_at=rng.randrange(1, high + 5))
        seed = rng.randrange(2**32)
        prompt = f"Câu hỏi {rng.randrange(10000)}: α + 2?"
        prefix = rng.choice(("", "Earlier reasoning.\n"))
        long, short = collect(model, prompt, high, seed), collect(model, prompt, low, seed)
        replay = score_replay(long, model.tokenizer, low,
                              {"family": "arith", "answer": "42"}, prefix_text=prefix)
        expected_parser = parse_answer_details(prefix + short["raw_output"], answer_type="number")
        assert replay["raw_output"] == short["raw_output"]
        assert replay["completion_token_ids"] == short["completion_token_ids"]
        assert replay["completion_tokens"] == short["completion_tokens"]
        assert replay["finish_reason"] == short["finish_reason"]
        assert (replay["parsed_answer"], replay["parse_status"], replay["wordy"]) == expected_parser
        parsed_successes += expected_parser[1] == "marker"
        finished_cases += replay["finished"]
        length_cases += not replay["finished"]
    assert parsed_successes > 0 and finished_cases > 0 and length_cases > 0


def test_t4_addendum_journal_carries_original_ids_and_decoding_provenance(tmp_path):
    output = tmp_path / "addendum"
    run_cot_restart_addendum(DEFAULT_HISTORICAL_DIR, output, mock=True)
    entries = [json.loads(line) for line in (output / "calls.jsonl").read_text().splitlines()]
    completed = [e["value"] for e in entries if e["kind"] == "addendum_call"]
    assert len(completed) == 12
    for record in completed:
        assert len(record["prompt_token_ids"]) == record["prompt_tokens"]
        assert len(record["completion_token_ids"]) == record["completion_tokens"]
        assert record["finish_reason"] in ("stop", "length")
        assert record["seed_policy"] == CAP_SWEEP_SEED_POLICY
        assert record["backend_version"] == "causal-mock-v1"
        assert record["tokenizer_version"]["implementation"] == "mock-four-character-v1"
        assert record["decoding_config"]["cap_only_stopping"]
        assert record["completion_token_scope"] == "sampled_tokens_including_terminal_eos"
    manifest = json.loads((output / "manifest.json").read_text())
    assert "experiments/cot_restart_replay.py" in manifest["source_hashes"]


def test_mock_cap_cuts_text_instead_of_only_reducing_reported_count():
    model = MockLLM()
    text, tokens, finish = model.generate("p", max_tokens=1, temp=.6, seed=42)
    assert len(model.tokenizer.encode(text)) == tokens == 1
    assert "Answer:" not in text
    assert finish == "length"


def test_cap_sweep_seed_is_stable_and_distinguishes_calls_and_arms():
    assert derive_cap_sweep_seed(42, "q1", "A") == derive_cap_sweep_seed(42, "q1", "A")
    assert len({derive_cap_sweep_seed(42, "q1", arm, call)
                for arm in ("A", "F", "CONT") for call in range(3)}) == 9


def test_replay_rejects_legacy_unknown_stops_bad_ids_and_increased_cap():
    model = MockLLM()
    record = collect(model, "p", 30)
    with pytest.raises(ValueError, match="text-only"):
        replay_completion({"raw_output": "Answer: 42"}, model.tokenizer, 10)
    with pytest.raises(ValueError, match="collected cap"):
        replay_completion(record, model.tokenizer, 31)
    corrupt = copy.deepcopy(record)
    corrupt["completion_token_ids"].append(12)
    with pytest.raises(ValueError, match="inconsistent"):
        replay_completion(corrupt, model.tokenizer, 10)
    corrupt = copy.deepcopy(record)
    corrupt["decoding_config"]["stop_strings"] = ["STOP"]
    with pytest.raises(ValueError, match="unsupported"):
        replay_completion(corrupt, model.tokenizer, 10)


def test_same_text_different_finish_when_eos_is_just_beyond_cap():
    model = MockLLM()
    long = collect(model, "p", 100)
    at_eos = long["completion_tokens"]
    before = replay_completion(long, model.tokenizer, at_eos - 1)
    after = replay_completion(long, model.tokenizer, at_eos)
    assert before["raw_output"] == after["raw_output"]
    assert before["finish_reason"] == "length" and after["finish_reason"] == "stop"


def test_native_replay_scores_only_after_thinking_closes():
    model = MockLLM()
    long = collect(model, "p", 100, thinking=True)
    item = {"family": "arith", "answer": "42"}
    short = score_replay(long, model.tokenizer, 2, item)
    assert short["parsed_answer"] is None and short["parse_status"] == "truncated_thinking"
    full = score_replay(long, model.tokenizer, 100, item)
    assert full["parse_status"] == "marker"


def test_replay_finalizes_buffered_streaming_text_at_the_cut():
    class BufferedTokenizer(MockLLM.MockTokenizer):
        @property
        def detokenizer(self):
            tokenizer = self

            class Decoder:
                def __init__(self):
                    self.ids, self.text, self.offset = [], "", 0

                def add_token(self, token):
                    self.ids.append(token)

                @property
                def last_segment(self):
                    segment = self.text[self.offset:]
                    self.offset = len(self.text)
                    return segment

                def finalize(self):
                    self.text = tokenizer.decode(self.ids)

            return Decoder()

    model = MockLLM()
    model.tokenizer = BufferedTokenizer()
    long = collect(model, "p", 100)
    long["text_decoder"] = "mlx_streaming_detokenizer"
    replay = replay_completion(long, model.tokenizer, 3)
    direct = collect(model, "p", 3)
    assert replay["raw_output"] == direct["raw_output"] != ""


def test_replay_rejects_changed_tokenizer_and_inconsistent_eos_flags():
    model = MockLLM()
    record = collect(model, "p", 100)
    changed = copy.deepcopy(record)
    changed["tokenizer_version"]["implementation"] = "different-renderer"
    with pytest.raises(ValueError, match="tokenizer_version"):
        replay_completion(changed, model.tokenizer, 10)
    changed = copy.deepcopy(record)
    changed["includes_eos"] = False
    with pytest.raises(ValueError, match="scope"):
        replay_completion(changed, model.tokenizer, 10)
    empty = replay_completion(record, model.tokenizer, 0, prefix_text="Keep this prefix.")
    assert empty["full_response"] == "Keep this prefix."
    assert empty["completion_tokens"] == 0 and empty["finish_reason"] == "length"


def test_t5_count_mismatch_blocks_even_when_text_roundtrip_matches():
    class Tokenizer:
        def encode(self, text, **kwargs):
            return SimpleNamespace(ids=list(text.encode()))

        def decode(self, ids, **kwargs):
            return bytes(ids).decode()

    rows = [{"key": ["call"], "raw_output": "abc", "finish_reason": "stop",
             "completion_tokens": 5}]
    audit = audit_rows(rows, Tokenizer())
    assert audit["roundtrip_matches"] == 1
    assert audit["eos_adjusted_count_matches"] == 0
    assert not audit["T5_eos_aware_pass"]
    assert not audit["original_token_identity_verified"]
