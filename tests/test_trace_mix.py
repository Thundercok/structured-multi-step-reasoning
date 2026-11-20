import json

import pytest

from structured_llm.trace_mix import SPLIT, build_nested_mixes, human_count


def _make_source(tmp_path, n=229):
    src = tmp_path / "src"
    for name in ("self", "human"):
        d = src / name
        d.mkdir(parents=True)
        rows = [{"text": f"<|im_start|>user\nQ{i}<|im_end|>\n{SPLIT}{name}_trace_{i}<|im_end|>"} for i in range(n)]
        (d / "train.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (d / "valid.jsonl").write_text('{"text": "valid"}\n')
    return src


def test_nested_mixes_counts_nesting_and_order(tmp_path):
    src = _make_source(tmp_path, n=229)
    out = tmp_path / "out"
    manifest = build_nested_mixes(src, out, ratios=(25, 50, 75), seed=20261120)

    assert manifest["n_rows"] == 229
    assert [manifest["ratios"][str(p)]["human_count"] for p in (25, 50, 75)] == [57, 114, 172]
    assert human_count(229, 0) == 0 and human_count(229, 100) == 229

    s25 = set(manifest["ratios"]["25"]["human_indices"])
    s50 = set(manifest["ratios"]["50"]["human_indices"])
    s75 = set(manifest["ratios"]["75"]["human_indices"])
    assert s25 < s50 < s75

    for pct, expected_set in ((25, s25), (50, s50), (75, s75)):
        rows = [json.loads(l)["text"] for l in (out / f"mix{pct}/train.jsonl").read_text().splitlines()]
        assert len(rows) == 229
        for i, text in enumerate(rows):
            prompt, trace = text.split(SPLIT, 1)
            assert prompt == f"<|im_start|>user\nQ{i}<|im_end|>\n"
            expected_prefix = f"human_trace_{i}" if i in expected_set else f"self_trace_{i}"
            assert trace.startswith(expected_prefix)
        assert (out / f"mix{pct}/valid.jsonl").read_text() == '{"text": "valid"}\n'


def test_nested_mixes_is_deterministic(tmp_path):
    src = _make_source(tmp_path, n=40)
    m1 = build_nested_mixes(src, tmp_path / "a", seed=20261120)
    m2 = build_nested_mixes(src, tmp_path / "b", seed=20261120)
    assert m1["ratios"] == m2["ratios"]


def test_nested_mixes_rejects_prompt_mismatch(tmp_path):
    src = _make_source(tmp_path, n=5)
    bad = src / "human/train.jsonl"
    lines = bad.read_text().splitlines()
    lines[2] = json.dumps({"text": f"<|im_start|>user\nWRONG<|im_end|>\n{SPLIT}human_trace_2<|im_end|>"})
    bad.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="prompt mismatch"):
        build_nested_mixes(src, tmp_path / "out")
