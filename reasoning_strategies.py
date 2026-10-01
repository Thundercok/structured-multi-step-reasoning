"""Phần logic không phụ thuộc model - test được mà không cần load Qwen3."""

import ast
import contextlib
import io
import multiprocessing as mp
import operator
import re
from collections import Counter

CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ANSWER_LINE = re.compile(r"answer\s*:\s*([^\n]+)", re.IGNORECASE)
ACTION_LINE = re.compile(r"Action:\s*(\w+)\[(.*?)\]", re.DOTALL)
NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def extract_answer(text: str) -> str:
    """Lấy dòng 'Answer: ...' cuối cùng; fallback dòng cuối không rỗng."""
    matches = ANSWER_LINE.findall(text)
    placeholders = {"<kết quả>", "<your final answer>", "[kết quả của bạn]", "<final answer>", "<answer>"}
    if matches:
        for cand in reversed(matches):
            c_clean = cand.strip().strip(".")
            if c_clean and c_clean not in placeholders:
                return c_clean
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    for l in reversed(lines):
        if l not in placeholders and not l.startswith("```"):
            return l
    return lines[-1] if lines else ""


def extract_number(text: str) -> str | None:
    """Số cuối cùng xuất hiện trong text, bỏ dấu phẩy ngăn cách nghìn. Dùng để so khớp đáp án GSM8K/MATH."""
    nums = NUM.findall(text.replace(",", ""))
    return nums[-1] if nums else None


def numeric_match(pred: str, gold: str, tol: float = 1e-4) -> bool:
    p, g = extract_number(pred), extract_number(gold)
    if p is None or g is None:
        return pred.strip().lower() == gold.strip().lower()
    try:
        return abs(float(p) - float(g)) <= tol
    except ValueError:
        return p == g


def parse_action(text: str) -> tuple[str, str] | None:
    m = ACTION_LINE.search(text)
    return (m.group(1).lower(), m.group(2).strip()) if m else None


def majority_vote(answers: list[str]) -> tuple[str, float]:
    if not answers:
        return "", 0.0
    vote, count = Counter(answers).most_common(1)[0]
    return vote, count / len(answers)


# ---------- calculator an toàn cho ReAct (chỉ số học, không eval()) ----------

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_arith(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_arith(node.left), _eval_arith(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNOPS:
        return _UNOPS[type(node.op)](_eval_arith(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


def safe_calculate(expr: str) -> str:
    """+-*/ ** % và ngoặc; không name, không call -> không thể inject code."""
    try:
        tree = ast.parse(expr, mode="eval")
        return str(_eval_arith(tree.body))
    except Exception as e:
        return f"error: {e}"


# ---------- sandbox Python cho PAL ----------

_SAFE_BUILTINS = {n: getattr(__builtins__, n) if not isinstance(__builtins__, dict) else __builtins__[n]
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
    if re.search(r"\b(import|open|exec|eval|__import__|__builtins__|subprocess|os\.)\b", code):
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
    return status == "ok", payload


def extract_code(text: str) -> str:
    m = CODE_FENCE.search(text)
    return (m.group(1) if m else text).strip()
