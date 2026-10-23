"""Audit-only exact reference: no production AST/check24 used for expected labels."""
from collections import Counter
from fractions import Fraction
import hashlib
from itertools import permutations
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.verifiers import verify_g24_rationale

OUT = Path(__file__).resolve().parent
RUN = ROOT / "audit/development-pilot-measured-20261004-runtimefix"
RECORDS_SHA = "1b1a79624c8b605627c6cb002fc473b62389f3da7700c39415772d62e7b4a3f0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UnsupportedExpression(ValueError):
    pass


def reference(expression, numbers):
    """Separate token/precedence-stack interpreter for public integer expressions."""
    if len(numbers) != 4 or any(type(n) is not int or n <= 0 for n in numbers):
        return "unverifiable", "unsupported input domain"
    expression = expression.replace("×", "*").replace("÷", "/").strip()
    parts = expression.split("=")
    if len(parts) not in (1, 2):
        return "unverifiable", "unsupported equality shape"
    if len(parts) == 2:
        rhs = parts[1].strip()
        if not re.fullmatch(r"\d+(?:\.\d+)?", rhs) or Fraction(rhs) != 24:
            return "invalid", "wrong or unsupported equality target"
    text = parts[0].strip()
    tokens, position = [], 0
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        match = re.match(r"\d+|[()+*/-]", text[position:])
        if match is None:
            return "unverifiable", "outside reference grammar"
        tokens.append(match.group())
        position += len(match.group())
    values, operators, used = [], [], []
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2}

    def reduce_once():
        if len(values) < 2:
            raise UnsupportedExpression("missing operand")
        op, right, left = operators.pop(), values.pop(), values.pop()
        if op == "+": values.append(left + right)
        elif op == "-": values.append(left - right)
        elif op == "*": values.append(left * right)
        elif op == "/": values.append(left / right)
        else: raise UnsupportedExpression("unmatched parenthesis")

    expecting_operand = True
    try:
        for token in tokens:
            if token.isdigit():
                if not expecting_operand or (len(token) > 1 and token[0] == "0"):
                    raise UnsupportedExpression("unsupported integer placement")
                used.append(int(token))
                values.append(Fraction(int(token)))
                expecting_operand = False
            elif token == "(":
                if not expecting_operand: raise UnsupportedExpression("implicit multiplication")
                operators.append(token)
            elif token == ")":
                if expecting_operand: raise UnsupportedExpression("empty or incomplete parentheses")
                while operators and operators[-1] != "(": reduce_once()
                if not operators: raise UnsupportedExpression("unmatched parenthesis")
                operators.pop()
                expecting_operand = False
            else:
                if expecting_operand: raise UnsupportedExpression("unary or missing operand")
                while operators and operators[-1] != "(" and precedence[operators[-1]] >= precedence[token]:
                    reduce_once()
                operators.append(token)
                expecting_operand = True
        if expecting_operand: raise UnsupportedExpression("missing final operand")
        while operators: reduce_once()
        if len(values) != 1: raise UnsupportedExpression("invalid expression shape")
    except ZeroDivisionError:
        return "invalid", "division by zero"
    except UnsupportedExpression as exc:
        return "unverifiable", str(exc)
    valid = values[0] == 24 and Counter(used) == Counter(numbers)
    return ("valid", "exact target and operand multiset") if valid else ("invalid", "wrong value or operand multiset")


def trees(numbers):
    """Construct all ordered full binary expressions and exact values, without parsing."""
    if len(numbers) == 1:
        yield str(numbers[0]), Fraction(numbers[0])
        return
    for split in range(1, len(numbers)):
        for left, a in trees(numbers[:split]):
            for right, b in trees(numbers[split:]):
                yield f"({left}+{right})", a + b
                yield f"({left}-{right})", a - b
                yield f"({left}*{right})", a * b
                if b:
                    yield f"({left}/{right})", a / b


def main():
    source_names = ("scripts/verifiers.py", "scripts/gen_tasks.py")
    source_before = {name: sha(ROOT / name) for name in source_names}
    manual = [
        ("1*2*3*4", [1, 2, 3, 4], "valid"),
        ("8/(3-8/3)", [3, 3, 8, 8], "valid"),
        ("5*(5-1/5)", [5, 5, 5, 1], "valid"),
        ("1+2+3+4", [1, 2, 3, 4], "invalid"),
        ("1*2*3*4=25", [1, 2, 3, 4], "invalid"),
        ("1*2*3*4", [1, 2, 3, 5], "invalid"),
        ("24", [1, 2, 3, 4], "invalid"),
        ("1/(2-2)*3", [1, 2, 2, 3], "invalid"),
        ("1+(", [1, 2, 3, 4], "unverifiable"),
        ("", [1, 2, 3, 4], "unverifiable"),
    ]
    assert all(reference(expr, nums)[0] == expected for expr, nums, expected in manual)
    synthetic, mismatches = [], []
    for numbers in ((1, 2, 3, 4), (3, 3, 8, 8), (5, 5, 5, 1), (1, 1, 1, 1)):
        expressions = {}
        for order in sorted(set(permutations(numbers))):
            for expression, value in trees(order):
                expressions[expression] = value
        counts = Counter()
        for expression, value in expressions.items():
            expected = value == 24
            ref_status, _ = reference(expression, list(numbers))
            assert (ref_status == "valid") == expected and ref_status != "unverifiable"
            counts["valid_by_construction" if expected else "invalid_by_construction"] += 1
            variants = [("same_inputs", list(numbers), expected)]
            if expected:
                variants += [("permuted_inputs", list(reversed(numbers)), True),
                             ("wrong_multiset", [*numbers[:-1], numbers[-1] + 1], False)]
            for kind, inputs, wanted in variants:
                status = verify_g24_rationale("Answer: " + expression, {"numbers": inputs}).status.value
                counts["checker_calls"] += 1
                if (status == "valid") != wanted:
                    mismatches.append({"expression": expression, "numbers": inputs, "kind": kind,
                                       "expected_valid": wanted, "actual_status": status})
        synthetic.append({"authored_numbers": numbers, "distinct_expressions": len(expressions), **counts})
    manifest = json.loads((RUN / "manifest.json").read_text())
    assert manifest["artifact_sha256"]["records.json"] == RECORDS_SHA
    hashes = manifest["artifact_sha256"]
    assert all(sha(RUN / name) == digest for name, digest in hashes.items())
    data = json.loads((RUN / "dataset.json").read_text())
    assert {i["split"] for i in data["items"]} <= {"train", "calibration"}
    inputs = {i["id"]: i["meta"]["numbers"] for i in data["items"] if i["family"] == "g24"}
    rows = [r for r in json.loads((RUN / "records.json").read_text())
            if r["family"] == "g24" and r["strategy"] == "COT" and r["token_budget"] == 1024]
    assert len(rows) == len({r["group_id"] for r in rows}) == 8
    coverage = []
    for row in rows:
        status, reason = reference(row["answer"], inputs[row["id"]])
        production = verify_g24_rationale("Answer: " + row["answer"], {"numbers": inputs[row["id"]]}).status.value
        coverage.append({"id": row["id"], "reference_status": status, "reference_reason": reason,
                         "checker_status": production, "stored_correct": row["correct"]})
    assert all(sha(RUN / name) == digest for name, digest in hashes.items())
    assert source_before == {name: sha(ROOT / name) for name in source_names}
    result = {
        "kind": "independent audit-only arithmetic reference", "new_model_calls": 0,
        "policy_fitting": False, "held_out_data_read": False,
        "manual_reference_controls": len(manual), "synthetic_subspaces": synthetic,
        "checker_acceptance_mismatches": mismatches,
        "reference_coverage_on_saved_development": dict(Counter(r["reference_status"] for r in coverage)),
        "saved_development_rows": coverage, "source_sha256": source_before,
        "probe_sha256": sha(Path(__file__)), "historical_artifact_sha256": hashes,
        "publication_ready": False,
        "scope": "Four authored number tuples, finite binary-expression grammar; eight exposed original groups. Not a proof for arbitrary input or model quality.",
    }
    (OUT / "independent_g24_reference.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("manual_reference_controls", "synthetic_subspaces", "checker_acceptance_mismatches", "reference_coverage_on_saved_development", "new_model_calls")}, indent=2))


if __name__ == "__main__":
    main()
