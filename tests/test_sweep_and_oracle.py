import json
from pathlib import Path
import pytest
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_oracle import synthetic_oracle_test, analyze_trace


def test_analyze_oracle_synthetic():
    res = synthetic_oracle_test(n_items=2000, p=0.5, seed=42)
    ora = res["oracle"]["accuracy"]
    bst = res["best_single"]["accuracy"]
    gap = res["gap"]["gap"]
    assert 0.97 <= ora <= 0.995
    assert 0.47 <= bst <= 0.54
    assert 0.45 <= gap <= 0.52

    ci_gap = res["gap"]["ci_95"]
    assert ci_gap[0] < gap < ci_gap[1] or abs(ci_gap[0] - gap) < 0.05


def test_run_sweep_stub_and_resume(tmp_path):
    out_jsonl = tmp_path / "stub_trace.jsonl"
    arms = "DIRECT-v2,COT,SC,TOT,REACT,PAL"

    # 1. First run: 2 items * 6 arms = 12 records
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_sweep.py"),
        "--dataset",
        str(ROOT / "data" / "gen02_tune.json"),
        "--arms",
        arms,
        "--out",
        str(out_jsonl),
        "--max-items",
        "2",
        "--stub",
    ]
    subprocess.check_call(cmd)

    records = [json.loads(line) for line in open(out_jsonl)]
    assert len(records) == 12, f"Expected 12 records (2 items * 6 arms), got {len(records)}"

    required_fields = [
        "id", "group_id", "family", "level", "arm", "model_id",
        "snapshot_dir", "snapshot_hash", "safetensors_blobs",
        "eos_token_ids", "enable_thinking", "branch", "tag",
        "commit", "dirty", "raw_output", "parsed", "gold", "correct",
        "prompt_tokens", "completion_tokens", "n_tokens", "mean_logprob", "min_logprob",
        "finish_reason", "wall_ms",
    ]
    for r in records:
        for f in required_fields:
            assert f in r, f"Missing header/trace field: {f} in record {r}"
        if r["arm"] == "SC":
            assert isinstance(r.get("sc_candidates"), list)
            assert isinstance(r.get("sc_vote_share"), (float, int))
        if r["arm"] == "TOT":
            assert isinstance(r.get("tot_candidates"), list)
            assert isinstance(r.get("tot_eval_scores"), list)

    # 2. Second run: resume should append 0 duplicates
    subprocess.check_call(cmd)
    records_after = [json.loads(line) for line in open(out_jsonl)]
    assert len(records_after) == 12, f"Expected exactly 12 records after resume, got {len(records_after)}"

    # 3. Analyze trace on stub records
    analysis = analyze_trace(records_after, n_bootstrap=50)
    assert analysis["n_items"] == 2
    assert len(analysis["arms"]) == 6


def test_get_git_info_untracked_dirty(tmp_path):
    from scripts.run_sweep import get_git_info

    # Initialize isolated git repository
    subprocess.check_call(["git", "init"], cwd=str(tmp_path))
    subprocess.check_call(["git", "config", "user.name", "Test Runner"], cwd=str(tmp_path))
    subprocess.check_call(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path))
    (tmp_path / "README.md").write_text("initial repo")
    subprocess.check_call(["git", "add", "README.md"], cwd=str(tmp_path))
    subprocess.check_call(["git", "commit", "-m", "init"], cwd=str(tmp_path))

    # 1. Clean repo initially
    info = get_git_info(cwd=tmp_path)
    assert info["dirty"] is False

    # 2. Files in audit/ should not trigger dirty
    (tmp_path / "audit").mkdir()
    (tmp_path / "audit" / "trace.jsonl").write_text("trace data")
    (tmp_path / "audit" / "summary.txt").write_text("summary data")
    assert get_git_info(cwd=tmp_path)["dirty"] is False

    # 3. Modified/created data/MANIFEST.json should not trigger dirty
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "MANIFEST.json").write_text("{}")
    assert get_git_info(cwd=tmp_path)["dirty"] is False

    # 4. Untracked file in project should trigger dirty == True
    dummy = tmp_path / "scripts" / "dummy_untracked.py"
    dummy.parent.mkdir(parents=True, exist_ok=True)
    dummy.write_text("print('untracked')")
    assert get_git_info(cwd=tmp_path)["dirty"] is True

