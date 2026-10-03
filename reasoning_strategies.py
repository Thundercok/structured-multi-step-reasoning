"""Phần logic không phụ thuộc model - test được mà không cần load Qwen3."""

import ast
import json
import operator
import re
import subprocess
import sys
from collections import Counter

CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ANSWER_LINE = re.compile(r"(?:\*\*)?answer(?:\*\*)?\s*:\s*([^\n]+)", re.IGNORECASE)
ACTION_LINE = re.compile(r"Action:\s*(\w+)\[(.*?)\]", re.DOTALL)
NUM = re.compile(r"-?\d[\d,]*\.?\d*")
NUMERIC_ANSWER = re.compile(r"^\s*-?\d[\d,]*\.?\d*(?:\s+[^\d]*)?\s*$")
EQUALS_RESULT = re.compile(r"=\s*(-?\d[\d,]*\.?\d*)")
TRAILING_NUMERIC_RESULT = re.compile(r"[:=]\s*(-?\d[\d,]*\.?\d*)(?:\s+[^\d]*)?\s*$")
YES_NO_ANSWER = re.compile(r"^\s*(yes|no)\b", re.IGNORECASE)


def normalize_answer(ans: str) -> str:
    """Format-only normalizer, never gold-based.

    1. Strip one balanced ** wrapping the whole answer/label.
    2. Collapse repeated leading "Answer:" or "Final Answer:".
    """
    s = (ans or "").strip()
    while True:
        before = s
        if s.startswith("**") and s.endswith("**") and len(s) >= 4:
            s = s[2:-2].strip()
        m = re.match(
            r"^(?:#{1,6}\s*)?(?:[^\w\s]+\s*)?(?:\*\*)?(?:final\s+)?answer(?:\*\*)?\s*:\s*",
            s,
            flags=re.IGNORECASE,
        )
        if m:
            s = s[m.end():].strip()
        if s.endswith(".") and not re.search(r"\d\.\d", s):
            s = s[:-1].strip()
        if s.startswith("**") and s.endswith("**") and len(s) >= 4:
            s = s[2:-2].strip()
        if s == before:
            break
    return s


def extract_answer(text: str, answer_type: str | None = None, decimal_separator: str = ".") -> str:
    """Lấy dòng 'Answer: ...' cuối cùng; fallback dòng cuối không rỗng."""
    if answer_type is not None:
        from research_scoring import parse_typed_answer
        return parse_typed_answer(text, answer_type, decimal_separator)[0]
    return parse_answer_details(text, decimal_separator=decimal_separator)[0]



def extract_number(text: str) -> str | None:
    """Số cuối cùng xuất hiện trong text, bỏ dấu phẩy ngăn cách nghìn. Dùng để so khớp đáp án GSM8K/MATH."""
    nums = NUM.findall(text.replace(",", ""))
    return nums[-1] if nums else None


def extract_conclusion_number(text: str) -> str | None:
    """Chuẩn hóa số chỉ khi chuỗi có hình thức đáp án hoặc tín hiệu kết luận."""
    lowered = text.casefold()
    conclusion_cues = (
        "therefore", "thus", "hence", "final answer", "kết quả", "đáp án",
        "do đó", "vậy", "total",
    )
    equals_results = EQUALS_RESULT.findall(text)
    if equals_results:
        return extract_number(equals_results[-1])
    trailing = TRAILING_NUMERIC_RESULT.search(text)
    if trailing:
        return extract_number(trailing.group(1))
    if NUMERIC_ANSWER.fullmatch(text) or any(cue in lowered for cue in conclusion_cues):
        return extract_number(text)
    return None


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


def is_wordy_answer(ans: str) -> bool:
    """True nếu Answer không phải số, không phải từ/tên đơn lẻ, và không phải biểu thức số học."""
    ans = (ans or "").strip()
    if not ans:
        return False
    if any(tok in ans for tok in ("\\", r"\text", r"\frac", "{", "}")):
        return True
    expr_chars = set("0123456789+-*/().= ×÷")
    if set(ans).issubset(expr_chars) and any(c.isdigit() for c in ans):
        return False
    num = extract_number(ans)
    if num is not None:
        words = ans.split()
        if len(words) <= 2:
            return False
    if re.fullmatch(r"[A-Za-z0-9_-]+\.?", ans):
        return False
    return True


def parse_answer_details(text: str, answer_type: str | None = None, decimal_separator: str = ".") -> tuple[str, str, bool]:
    """
    Trích xuất đáp án và phân loại:
    Returns (answer, parse_status, wordy).
    parse_status in {"marker", "fallback", "fail"}.
    wordy: True nếu answer không phải số, từ/tên, hay biểu thức.
    'fail' gồm cả chuỗi rỗng, câu giải thích dài, và LaTeX.
    """
    if answer_type is not None:
        from research_scoring import parse_typed_answer
        return parse_typed_answer(text, answer_type, decimal_separator)

    lines = text.splitlines()
    marker_re = re.compile(
        r"(?:#{1,6}\s*)?(?:[^\w\s]+\s*)?(?:\*\*)?(?:final\s+)?answer(?:\*\*)?\s*:\s*(.*)",
        re.IGNORECASE,
    )
    ans = ""
    status = "fail"

    def _clean_cand(norm: str) -> str:
        is_expr = any(op in norm for op in ("+", "*", "/", "×", "÷")) or ("=" in norm and not re.match(r"^-\d", norm.strip()))
        if not is_expr:
            num = extract_conclusion_number(norm)
            if num is not None:
                return num
        return norm

    # 1. Search backwards for marker line (accept same line or next line)
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        m = marker_re.search(line)
        if m:
            val = m.group(1).strip()
            if line.startswith("**") and line.endswith("**") and len(line) >= 4:
                val = line
            if val:
                norm = normalize_answer(val)
                if norm:
                    ans = _clean_cand(norm)
                    status = "marker"
                    break
            # Check next non-empty line
            for j in range(i + 1, len(lines)):
                next_l = lines[j].strip()
                if next_l and not next_l.startswith("```"):
                    norm = normalize_answer(next_l)
                    if norm:
                        ans = _clean_cand(norm)
                        status = "marker"
                        break
            if ans:
                break

    # 2. Fallback to last non-empty line
    if not ans:
        placeholders = {"<kết quả>", "<your final answer>", "[kết quả của bạn]", "<final answer>", "<answer>"}
        for l in reversed(lines):
            l = l.strip()
            if not l or l.startswith("```") or l.casefold() in placeholders:
                continue
            yes_no = YES_NO_ANSWER.match(l)
            if yes_no:
                ans = yes_no.group(1)
                status = "fallback"
                break
            num = extract_conclusion_number(l)
            if num is not None:
                ans = num
                status = "fallback"
                break
            norm = normalize_answer(l)
            if norm and norm.casefold() not in placeholders:
                ans = norm
                status = "fallback"
                break

    wordy = is_wordy_answer(ans)
    if not ans or wordy or any(tok in ans for tok in ("\\", r"\text", "{", "}")):
        status = "fail"

    return ans, status, wordy


def canonicalize_answer(s: str) -> str:
    """Chuẩn hoá: số -> số; text -> lower/strip; biểu thức -> bỏ khoảng trắng."""
    s = (s or "").strip()
    if not s:
        return ""
    is_expr = any(op in s for op in ("+", "*", "/", "=")) or ("-" in s and not re.match(r"^-\d", s.strip()))
    has_ordinal = re.search(r"\d(?:st|nd|rd|th)\b", s, re.IGNORECASE) is not None
    num = None if has_ordinal else extract_number(s)
    if num is not None and not is_expr:
        try:
            f = float(num)
            if f.is_integer():
                return str(int(f))
            return str(f)
        except ValueError:
            pass
    if is_expr and any(c.isdigit() for c in s):
        expr_body = s.split("=")[-1] if "=" in s and not s.strip().endswith("=") else s
        return "".join(expr_body.split())
    return s.strip().lower()


def majority_vote(answers: list[str], return_tie: bool = False, answer_type: str | None = None, decimal_separator: str = ".") -> tuple[str, float] | tuple[str, float, bool]:
    """Vote trên dạng chuẩn hoá, trả dạng chuẩn hoá. Hoà phiếu -> mẫu đầu, ghi tie=True."""
    if not answers:
        return ("", 0.0, False) if return_tie else ("", 0.0)
    if answer_type is None:
        canonical_list = [canonicalize_answer(a) for a in answers]
    else:
        from research_scoring import typed_vote_key
        canonical_list = [typed_vote_key(a, answer_type, decimal_separator) for a in answers]
    counts = Counter(canonical_list)
    most_common = counts.most_common()
    max_count = most_common[0][1]
    top_candidates = [cand for cand, count in most_common if count == max_count]
    is_tie = len(top_candidates) > 1 and len(answers) > 1
    if is_tie:
        winner = next(c for c in canonical_list if c in top_candidates)
    else:
        winner = top_candidates[0]
    ratio = max_count / len(answers)
    if return_tie:
        return winner, ratio, is_tie
    return winner, ratio


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

_PAL_RUNNER = r"""
import builtins
import contextlib
import io
import json
import sys

names = (
    "print", "abs", "min", "max", "sum", "round", "len", "range", "sorted",
    "int", "float", "str", "list", "dict", "tuple", "set", "enumerate", "zip",
)
namespace = {"__builtins__": {name: getattr(builtins, name) for name in names}}
buffer = io.StringIO()
try:
    with contextlib.redirect_stdout(buffer):
        exec(sys.stdin.read(), namespace)
    output = buffer.getvalue().strip()
    value = str(namespace.get("result", "")).strip()
    if not value and output:
        value = output.splitlines()[-1].strip()
    if not value:
        raise ValueError("code produced no result")
    print(json.dumps(["ok", value]))
except Exception as error:
    print(json.dumps(["error", f"{type(error).__name__}: {error}"]))
"""


def run_python_sandboxed(code: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Chạy code trong interpreter con tối thiểu, không import lại MLX/Metal.

    Builtins bị giới hạn và import/open/exec/eval bị chặn. Đây là helper cho
    môi trường thí nghiệm được kiểm soát, không phải security boundary.
    Trả (thành_công, ket_qua_hoac_loi). Code nên gán kết quả vào `result`.
    """
    if re.search(r"\b(import|open|exec|eval|__import__|__builtins__|subprocess|os\.)\b", code):
        return False, "blocked keyword in code"
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", _PAL_RUNNER],
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "timeout"
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"worker exited {completed.returncode}"
        return False, detail
    try:
        status, payload = json.loads(completed.stdout)
    except (ValueError, TypeError):
        return False, "invalid worker response"
    return status == "ok", payload


def extract_code(text: str) -> str:
    m = CODE_FENCE.search(text)
    return (m.group(1) if m else text).strip()
