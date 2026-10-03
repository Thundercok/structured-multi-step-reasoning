import os
import subprocess
import tempfile
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

def make_diff(file_rel, mutated_text):
    orig_path = os.path.join(ROOT, file_rel)
    with open(orig_path, "r", encoding="utf-8") as f:
        orig_text = f.read()
    
    with tempfile.NamedTemporaryFile("w", delete=False) as f_orig, \
         tempfile.NamedTemporaryFile("w", delete=False) as f_new:
        f_orig.write(orig_text)
        f_new.write(mutated_text)
        f_orig.flush()
        f_new.flush()
        cmd = ["diff", "-u", f"--label=a/{file_rel}", f"--label=b/{file_rel}", f_orig.name, f_new.name]
        res = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(f_orig.name)
        os.unlink(f_new.name)
        return res.stdout

def create_mutant_1(backend_code):
    # Revert generation prompt and finish_reason
    code = backend_code.replace(
        "prompt = self.tokenizer.apply_chat_template(\n            messages,\n            enable_thinking=False,\n            add_generation_prompt=True,\n        )",
        "prompt = self.tokenizer.apply_chat_template(messages, enable_thinking=False)",
    )
    code = code.replace("        finish_reason = None\n", "")
    code = code.replace("            if getattr(r, \"finish_reason\", None) is not None:\n                finish_reason = r.finish_reason\n", "")
    code = code.replace("                \"finish_reason\": finish_reason,\n", "")
    return code

def create_mutant_1b(backend_code):
    # Keep add_generation_prompt=True, revert ONLY finish_reason
    code = backend_code.replace("        finish_reason = None\n", "")
    code = code.replace("            if getattr(r, \"finish_reason\", None) is not None:\n                finish_reason = r.finish_reason\n", "")
    code = code.replace("                \"finish_reason\": finish_reason,\n", "")
    return code

def create_mutant_2(backend_code):
    # Revert REACT_SYSTEM and REACT_EXAMPLE
    old_react_sys = (
        'REACT_SYSTEM = (\n'
        '    "Giải bài toán bằng ReAct. Mỗi lượt chỉ viết:\\n"\n'
        '    "Thought: <suy nghĩ>\\nAction: calculate[bieu_thuc_so_hoc] hoặc Action: finish[dap_an]\\n"\n'
        '    "Không tự viết dòng Observation - hệ thống sẽ cung cấp sau khi bạn gọi calculate."\n'
        ')'
    )
    start = backend_code.find("REACT_SYSTEM = (")
    end = backend_code.find("PAL_SUFFIX = ", start)
    code = backend_code[:start] + old_react_sys + "\n" + backend_code[end:]
    
    # Revert _react msgs
    old_msgs = "msgs = [{\"role\": \"system\", \"content\": REACT_SYSTEM}, {\"role\": \"user\", \"content\": query}]"
    target_msgs = """msgs = [
            {"role": "system", "content": REACT_SYSTEM},
            *REACT_EXAMPLE,
            {"role": "user", "content": query},
        ]"""
    code = code.replace(target_msgs, old_msgs)
    return code

def create_mutant_3(strategies_code):
    # Revert imports and run_python_sandboxed
    code = strategies_code.replace(
        "import json\nimport operator\nimport re\nimport subprocess\nimport sys",
        "import contextlib\nimport io\nimport multiprocessing as mp\nimport operator\nimport re",
    )
    old_sandbox = '''_SAFE_BUILTINS = {n: getattr(__builtins__, n) if not isinstance(__builtins__, dict) else __builtins__[n]
                   for n in ("print", "abs", "min", "max", "sum", "round", "len", "range", "sorted",
                              "int", "float", "str", "list", "dict", "tuple", "set", "enumerate", "zip")}


def _worker(code: str, q: mp.Queue) -> None:
    ns = {"__builtins__": _SAFE_BUILTINS}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, ns)
        out = buf.getvalue().strip()
        val = str(ns.get("result", "")).strip()
        if not val and out:
            val = out.splitlines()[-1].strip()
        q.put(("ok", val))
    except Exception as e:
        q.put(("error", f"{type(e).__name__}: {e}"))


def run_python_sandboxed(code: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Chạy code trong process con, builtins bị giới hạn, không import/open/exec/eval.
    Trả (thành_công, ket_qua_hoac_loi). result phải được code gán vào biến `result`.
    """
    if re.search(r"\\b(import|open|exec|eval|__import__|__builtins__|subprocess|os\\.)\\b", code):
        return False, "blocked keyword in code"
    q: mp.Queue = mp.Queue()
    p = mp.Process(target=_worker, args=(code, q))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return False, "timeout"
    if q.empty():
        return False, "no result (crashed?)"
    status, payload = q.get()
    return status == "ok", payload'''

    start = code.find("_PAL_RUNNER = ")
    end = code.find("def extract_code(", start)
    code = code[:start] + old_sandbox + "\n\n\n" + code[end:]
    return code

def create_mutant_4(strategies_code):
    # Revert extract_answer and remove extract_conclusion_number + regexes
    code = strategies_code.replace(
        'ANSWER_LINE = re.compile(r"(?:\\*\\*)?answer(?:\\*\\*)?\\s*:\\s*([^\\n]+)", re.IGNORECASE)\nACTION_LINE = re.compile(r"Action:\\s*(\\w+)\\[(.*?)\\]", re.DOTALL)\nNUM = re.compile(r"-?\\d[\\d,]*\\.?\\d*")\nNUMERIC_ANSWER = re.compile(r"^\\s*-?\\d[\\d,]*\\.?\\d*(?:\\s+[^\\d]*)?\\s*$")\nEQUALS_RESULT = re.compile(r"=\\s*(-?\\d[\\d,]*\\.?\\d*)")\nTRAILING_NUMERIC_RESULT = re.compile(r"[:=]\\s*(-?\\d[\\d,]*\\.?\\d*)(?:\\s+[^\\d]*)?\\s*$")\nYES_NO_ANSWER = re.compile(r"^\\s*(yes|no)\\b", re.IGNORECASE)',
        'ANSWER_LINE = re.compile(r"answer\\s*:\\s*([^\\n]+)", re.IGNORECASE)\nACTION_LINE = re.compile(r"Action:\\s*(\\w+)\\[(.*?)\\]", re.DOTALL)\nNUM = re.compile(r"-?\\d[\\d,]*\\.?\\d*")',
    )
    old_extract = '''def extract_answer(text: str) -> str:
    """Lấy dòng 'Answer: ...' cuối cùng; fallback dòng cuối không rỗng."""
    matches = ANSWER_LINE.findall(text)
    placeholders = {"<kết quả>", "<suy nghĩ>", "bieu_thuc_so_hoc", "dap_an"}
    if matches:
        for cand in reversed(matches):
            c_clean = cand.strip().strip(".")
            if c_clean and c_clean not in placeholders:
                return c_clean
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    for l in reversed(lines):
        if l not in placeholders and not l.startswith("```"):
            return l
    return lines[-1] if lines else ""'''

    start = code.find("def extract_answer(text: str) -> str:")
    end = code.find("def extract_number(text: str) -> str | None:")
    code = code[:start] + old_extract + "\n\n\n" + code[end:]

    # Remove extract_conclusion_number
    start2 = code.find("def extract_conclusion_number(text: str) -> str | None:")
    end2 = code.find("def numeric_match(pred: str, gold: str, tol: float = 1e-4) -> bool:")
    code = code[:start2] + code[end2:]
    return code

def create_mutant_5(backend_code):
    # Revert ToT candidate selection and extract_best_index
    old_tot = '''        eval_prompt = f"Câu hỏi: {query}\\n\\nCác lời giải ứng viên:\\n{listing}\\n\\nChọn lời giải ĐÚNG nhất. Trả đúng 1 dòng 'Best: <chỉ số>'."
        eval_text, eval_conf, eval_tok = self._chat([{"role": "user", "content": eval_prompt}], temp=0.0)
        total_tok += eval_tok
        idx = extract_number_or_none(eval_text)
        best = candidates[idx] if idx is not None and idx < branches else candidates[0]
        return extract_answer(best), eval_conf, total_tok'''
    start = backend_code.find("eval_prompt = (")
    end = backend_code.find("def _react(self,", start)
    backend_code = backend_code[:start] + old_tot.strip() + "\n\n    " + backend_code[end:]

    old_extract = '''def extract_number_or_none(text: str) -> int | None:
    import re

    m = re.search(r"\\d+", text)
    return int(m.group()) if m else None'''
    start2 = backend_code.find("def extract_best_index(text: str, branches: int) -> int | None:")
    end2 = backend_code.find("if __name__ == \"__main__\":", start2)
    backend_code = backend_code[:start2] + old_extract + "\n\n\n" + backend_code[end2:]
    return backend_code

def main():
    with open(os.path.join(ROOT, "qwen_mlx_backend.py"), "r", encoding="utf-8") as f:
        b_code = f.read()
    with open(os.path.join(ROOT, "reasoning_strategies.py"), "r", encoding="utf-8") as f:
        s_code = f.read()

    mutants = {
        "patch_1.diff": ("qwen_mlx_backend.py", create_mutant_1(b_code)),
        "patch_1b.diff": ("qwen_mlx_backend.py", create_mutant_1b(b_code)),
        "patch_2.diff": ("qwen_mlx_backend.py", create_mutant_2(b_code)),
        "patch_3.diff": ("reasoning_strategies.py", create_mutant_3(s_code)),
        "patch_4.diff": ("reasoning_strategies.py", create_mutant_4(s_code)),
        "patch_5.diff": ("qwen_mlx_backend.py", create_mutant_5(b_code)),
    }

    os.makedirs(os.path.join(ROOT, "audit", "mutants"), exist_ok=True)

    for patch_name, (file_rel, mut_text) in mutants.items():
        diff = make_diff(file_rel, mut_text)
        patch_path = os.path.join(ROOT, "audit", "mutants", patch_name)
        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(diff)
        
        # Test git apply --check
        res = subprocess.run(["git", "apply", "--check", patch_path], cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"ERROR: {patch_name} failed git apply --check:\n{res.stderr}")
            sys.exit(1)
        print(f"SUCCESS: {patch_name} valid git patch for {file_rel}")

if __name__ == "__main__":
    main()
