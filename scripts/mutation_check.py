"""Mutation check runner for NCKH reasoning harness.

For each bug i (1..5), creates a mutant with ONLY the hunk for bug i reverted in a temporary worktree,
runs all 5 regression tests, asserts mutant i -> test i RED, and outputs the mutation matrix.
"""

import os
import shutil
import subprocess
import sys
import tempfile

TEST_NAMES = [
    "test_regression_generation_boundary_and_stop_token",
    "test_regression_react_placeholder_rejection",
    "test_regression_pal_timeout_and_sandbox_safety",
    "test_regression_parser_does_not_pick_wrong_trailing_token_or_unit",
    "test_regression_tot_selects_correct_candidate_branch",
]

PYTHON_EXE = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"


def run_tests_in_dir(worktree_dir: str) -> dict[str, tuple[bool, str]]:
    """Runs the 5 regression tests in worktree_dir and returns {test_name: (passed, failure_summary)}."""
    cmd = [
        PYTHON_EXE,
        "-m",
        "pytest",
        "tests/test_harness_regressions.py",
        "-v",
        "--timeout=20",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{worktree_dir}:{env.get('PYTHONPATH', '')}"
    env["QT_QPA_PLATFORM"] = "offscreen"
    res = subprocess.run(
        cmd,
        cwd=worktree_dir,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    results = {}
    for test in TEST_NAMES:
        # Check if test passed or failed in stdout
        passed = f"::{test} PASSED" in res.stdout
        # Extract short failure reason if failed
        failure_msg = ""
        if not passed:
            # find failure block
            if f"::{test} FAILED" in res.stdout:
                marker = f"_{test}_"
                start = res.stdout.find(marker)
                if start != -1:
                    snippet = res.stdout[start:start + 1200]
                    lines = [line.strip() for line in snippet.splitlines() if line.strip().startswith("E ")]
                    if lines:
                        failure_msg = lines[-1]
            if not failure_msg:
                failure_msg = "FAILED (assertion or exception)"
        results[test] = (passed, failure_msg)
    return results


def apply_mutant(worktree_dir: str, mutant_id: int):
    """Mutates worktree_dir by reverting ONLY the hunk corresponding to mutant_id."""
    backend_path = os.path.join(worktree_dir, "qwen_mlx_backend.py")
    strategies_path = os.path.join(worktree_dir, "reasoning_strategies.py")

    with open(backend_path, "r", encoding="utf-8") as f:
        backend_code = f.read()
    with open(strategies_path, "r", encoding="utf-8") as f:
        strategies_code = f.read()

    if mutant_id == 1:
        # Revert Bug 1: remove add_generation_prompt=True and finish_reason tracking
        target = "prompt = self.tokenizer.apply_chat_template(\n            messages,\n            enable_thinking=False,\n            add_generation_prompt=True,\n        )"
        replacement = "prompt = self.tokenizer.apply_chat_template(\n            messages,\n            enable_thinking=False,\n        )"
        assert target in backend_code, "Target for Mutant 1 not found"
        backend_code = backend_code.replace(target, replacement)
        # Also remove finish_reason
        backend_code = backend_code.replace(
            'if getattr(r, "finish_reason", None) is not None:\n                finish_reason = r.finish_reason',
            '# finish_reason removed'
        )

    elif mutant_id == 2:
        # Revert Bug 2: ReAct placeholder copying in REACT_SYSTEM and parser leak
        old_react_sys = (
            'REACT_SYSTEM = (\n'
            '    "Giải bài toán bằng ReAct. Mỗi lượt chỉ viết:\\n"\n'
            '    "Thought: <suy nghĩ>\\nAction: calculate[bieu_thuc_so_hoc] hoặc Action: finish[dap_an]\\n"\n'
            '    "Không tự viết dòng Observation - hệ thống sẽ cung cấp sau khi bạn gọi calculate."\n'
            ')'
        )
        assert "REACT_SYSTEM = (" in backend_code
        # replace REACT_SYSTEM block
        start = backend_code.find("REACT_SYSTEM = (")
        end = backend_code.find("PAL_SUFFIX = ", start)
        backend_code = backend_code[:start] + old_react_sys + "\n" + backend_code[end:]

        # in reasoning_strategies.py, revert placeholder check in extract_answer
        target = "if placeholder_prefix and number is None:\n                    continue"
        replacement = "# placeholder check disabled"
        assert target in strategies_code, "Target for Mutant 2 not found in strategies"
        strategies_code = strategies_code.replace(target, replacement)

    elif mutant_id == 3:
        # Revert Bug 3: PAL runner does not reject scripts with missing result
        target = 'if not value:\n        raise ValueError("code produced no result")'
        replacement = '# missing result check disabled'
        assert target in strategies_code, "Target for Mutant 3 not found"
        strategies_code = strategies_code.replace(target, replacement)

    elif mutant_id == 4:
        # Revert Bug 4: remove conclusion cues fallback from extract_conclusion_number
        target = "if NUMERIC_ANSWER.fullmatch(text) or any(cue in lowered for cue in conclusion_cues):\n        return extract_number(text)"
        replacement = "if NUMERIC_ANSWER.fullmatch(text):\n        return extract_number(text)"
        assert target in strategies_code, "Target for Mutant 4 not found"
        strategies_code = strategies_code.replace(target, replacement)

    elif mutant_id == 5:
        # Revert Bug 5: ToT candidate selection parses greedy number rather than Best: [i]
        # Keep add_generation_prompt=True completely untouched!
        target_eval = """        idx = extract_best_index(eval_text, branches)
        if idx is None:
            answer, _ = majority_vote(answers)
            selection = "majority_fallback"
        else:
            answer = answers[idx]
            selection = "model_index"
        self._record_tool({
            "name": "candidate_selector",
            "candidate_answers": answers,
            "selector_output": eval_text,
            "selected_index": idx,
            "selection": selection,
        })
        return answer, eval_conf, total_tok"""

        replacement_eval = """        import re
        m = re.search(r"\\d+", eval_text)
        idx = int(m.group()) if m else None
        best = candidates[idx] if idx is not None and idx < branches else candidates[0]
        return extract_answer(best), eval_conf, total_tok"""

        assert target_eval in backend_code, "Target for Mutant 5 not found"
        backend_code = backend_code.replace(target_eval, replacement_eval)

    with open(backend_path, "w", encoding="utf-8") as f:
        f.write(backend_code)
    with open(strategies_path, "w", encoding="utf-8") as f:
        f.write(strategies_code)


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    temp_dir = tempfile.mkdtemp(prefix="nckh_worktree_mutant_")
    print(f"Creating temporary worktree at {temp_dir}...")
    subprocess.run(["git", "worktree", "add", "--detach", temp_dir, "HEAD"], cwd=root_dir, check=True)

    try:
        # Copy current tests/test_harness_regressions.py to worktree
        shutil.copy(
            os.path.join(root_dir, "tests", "test_harness_regressions.py"),
            os.path.join(temp_dir, "tests", "test_harness_regressions.py"),
        )

        matrix = {}
        failure_details = {}

        # 0. Test Base
        print("\n--- Testing BASE (fixed code) ---")
        base_res = run_tests_in_dir(temp_dir)
        matrix["Base (all fixes)"] = [base_res[t][0] for t in TEST_NAMES]
        for t in TEST_NAMES:
            status = "PASS" if base_res[t][0] else "FAIL"
            print(f"  {t}: {status}")

        # 1..5 Mutants
        for i in range(1, 6):
            print(f"\n--- Testing MUTANT {i} (reverting Bug {i}) ---")
            # reset worktree to clean HEAD
            subprocess.run(["git", "checkout", "."], cwd=temp_dir, check=True)
            shutil.copy(
                os.path.join(root_dir, "tests", "test_harness_regressions.py"),
                os.path.join(temp_dir, "tests", "test_harness_regressions.py"),
            )
            apply_mutant(temp_dir, i)

            mutant_res = run_tests_in_dir(temp_dir)
            matrix[f"Mutant {i}"] = [mutant_res[t][0] for t in TEST_NAMES]
            failure_details[f"Mutant {i}"] = {t: mutant_res[t][1] for t in TEST_NAMES if not mutant_res[t][0]}

            for idx, t in enumerate(TEST_NAMES, start=1):
                passed, msg = mutant_res[t]
                status = "PASS" if passed else f"FAIL ({msg})"
                print(f"  Test {idx} ({t}): {status}")

        # Print Markdown Table
        print("\n" + "=" * 80)
        print("MUTATION CHECK RESULTS (MUTANT × TEST MATRIX)")
        print("=" * 80)
        headers = ["Variant / Mutant", "Test 1 (Boundary)", "Test 2 (ReAct)", "Test 3 (PAL)", "Test 4 (Parser)", "Test 5 (ToT)"]
        print("| " + " | ".join(headers) + " |")
        print("| " + " | ".join(["---"] * len(headers)) + " |")

        for name, row in matrix.items():
            symbols = ["🟩 PASS" if val else "🟥 FAIL" for val in row]
            print(f"| {name:<22} | " + " | ".join(symbols) + " |")

        print("\n" + "=" * 80)
        print("FAILURE DETAILS FOR RED TESTS")
        print("=" * 80)
        for mutant_name, details in failure_details.items():
            print(f"\n{mutant_name}:")
            for test_name, reason in details.items():
                print(f"  - {test_name}: {reason}")

    finally:
        print(f"\nCleaning up temporary worktree at {temp_dir}...")
        subprocess.run(["git", "worktree", "remove", "--force", temp_dir], cwd=root_dir, check=False)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
