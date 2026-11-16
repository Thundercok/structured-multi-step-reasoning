import json

from structured_llm import gsm8k, self_traces


def _row(question, answer):
    return {"question": question, "answer": answer}


ROWS = [
    _row("Tom has 3 apples and buys 4 more. How many?", "He has 3+4=<<3+4=7>>7 apples.\n#### 7"),
    _row("A box holds 5 pens. How many pens in 2 boxes?", "There are 5*2=<<5*2=10>>10 pens.\n#### 10"),
]


def _record(row, output, **check):
    base = {"format_valid": True, "errors": [], "correct": True, "calc_accuracy": 1.0}
    return {"id": gsm8k.rank_key(row["question"])[:16], "question": row["question"], "output": output,
            "truncated": False, "check": {**base, **check}}


def test_build_pairs_self_and_human_traces_on_the_same_questions(tmp_path, monkeypatch):
    monkeypatch.setattr(gsm8k, "load_splits", lambda: (ROWS, [], []))
    monkeypatch.setattr(self_traces, "keep", lambda r: None if r["check"]["correct"] else "wrong_answer")
    own = "<think>\nStep 1: Add: 3+4 = 7\nCalc: 3+4=7\n</think>\n\nAnswer: 7\n"
    records = [_record(ROWS[0], own), _record(ROWS[1], "x", correct=False)]
    eval_path = tmp_path / "base_prefill.jsonl"
    eval_path.write_text("".join(json.dumps(r) + "\n" for r in records))
    valid = tmp_path / "valid.jsonl"
    valid.write_text('{"text": "v"}\n')

    manifest = self_traces.build(eval_path, tmp_path / "out", valid=valid)

    assert manifest["kept"] == 1 and manifest["dropped"] == {"wrong_answer": 1}
    self_rows = [json.loads(l) for l in (tmp_path / "out/self/train.jsonl").read_text().splitlines()]
    human_rows = [json.loads(l) for l in (tmp_path / "out/human/train.jsonl").read_text().splitlines()]
    prompt = gsm8k.chatml_prompt(ROWS[0]["question"])
    assert self_rows == [{"text": prompt + own.strip() + "<|im_end|>"}]
    assert human_rows[0]["text"].startswith(prompt) and human_rows[0]["text"] != self_rows[0]["text"]
    assert (tmp_path / "out/human/valid.jsonl").read_text() == valid.read_text()


def test_train_items_skips_rows_without_a_human_trace(monkeypatch):
    bad = _row("No annotations here?", "Just words.\n#### 1")
    monkeypatch.setattr(gsm8k, "load_splits", lambda: ([bad, *ROWS], [], []))
    items = self_traces.train_items(5)
    assert [i["answer"] for i in items] == ["7", "10"]


def test_keep_is_strict():
    row = ROWS[0]
    assert self_traces.keep(_record(row, "x")) is None
    assert self_traces.keep({**_record(row, "x"), "truncated": True}) == "truncated"
    assert self_traces.keep(_record(row, "x", format_valid=False)) == "bad_format"
    assert self_traces.keep(_record(row, "x", errors=["e"])) == "bad_format"
    assert self_traces.keep(_record(row, "x", correct=False)) == "wrong_answer"
    assert self_traces.keep(_record(row, "x", calc_accuracy=0.8)) == "wrong_calc"
