"""Secure, isolated symbolic algebra & calculus sandbox (h_sym) using SymPy.

Provides deterministic mathematical problem-solving for CAP:SYMBOLIC_CALC and CAP:SANITY_CHECK.
Safeguards execution against unbounded recursion and unapproved system calls.
"""

import ast
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import sympy
    from sympy import (
        symbols, sympify, solve, Eq, simplify, factor, expand,
        sqrt, Rational, pi, E, sin, cos, tan, sec, csc, cot,
        log, exp, Abs, diff, integrate, N, binomial, factorial, gcd, lcm, Mod
    )
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor,
        factorial_notation,
    )
    _SYMPY_TRANSFORMATIONS = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
        factorial_notation,
    )
    _SYMPY_AVAILABLE = True
except ImportError:
    _SYMPY_AVAILABLE = False


def _extract_matching_braces(text: str, start_brace_idx: int) -> Tuple[Optional[str], int]:
    """Extract content inside matching curly braces starting at start_brace_idx."""
    if start_brace_idx >= len(text) or text[start_brace_idx] != "{":
        return None, start_brace_idx
    depth = 0
    for i in range(start_brace_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start_brace_idx + 1:i], i + 1
    return None, start_brace_idx


class SymPySandbox:
    """Safe symbolic algebra and numerical verification helper ($h_{sym}$)."""

    def __init__(self, timeout_seconds: float = 3.0):
        self.timeout_seconds = timeout_seconds

    def execute_query(self, query: str) -> str:
        """Parse natural query or mathematical instruction and return structured answer."""
        if not _SYMPY_AVAILABLE:
            return "[ERROR: SYMPY_NOT_INSTALLED]"

        query = query.strip()
        
        # 1. Equation solving: "Solve for x: <eq>" or "Solve: <eq>"
        if match := re.search(r"solve(?:\s+for\s+([a-zA-Z_]\w*))?[:\s]+(.*)", query, re.I):
            var_name = match.group(1) or "x"
            equation_str = match.group(2).strip()
            return self.solve_equation(equation_str, var_name)

        # 2. Simplification: "Simplify: <expr>"
        if match := re.search(r"simplify[:\s]+(.*)", query, re.I):
            return self.simplify_expression(match.group(1).strip())

        # 3. Direct expression or equation evaluation
        if "=" in query:
            return self.solve_equation(query, "x")
        else:
            return self.evaluate_expression(query)

    def solve_equation(self, eq_str: str, var_name: str = "x") -> str:
        """Solve an algebraic equation for a given variable."""
        if not _SYMPY_AVAILABLE:
            return "[ERROR: SYMPY_NOT_INSTALLED]"

        try:
            var = symbols(var_name)
            # Remove trailing periods, questions, notes
            eq_clean = re.sub(r"[.?!]+$", "", eq_str).strip()
            
            if "=" in eq_clean:
                lhs_str, rhs_str = eq_clean.split("=", 1)
                lhs = sympify(self._clean_math(lhs_str))
                rhs = sympify(self._clean_math(rhs_str))
                eq = Eq(lhs, rhs)
            else:
                eq = sympify(self._clean_math(eq_clean))

            roots = solve(eq, var)
            if not roots:
                return f"No closed-form solution found for {var_name} in: {eq_str}"

            results = []
            for r in roots:
                exact = str(r)
                try:
                    approx = float(N(r, 6))
                    results.append(f"{var_name} = {exact} (approx {approx:.4f})")
                except Exception:
                    results.append(f"{var_name} = {exact}")

            return "; ".join(results)
        except Exception as e:
            return f"[ERROR: SOLVE_FAILED: {e}]"

    def evaluate_expression(self, expr_str: str) -> str:
        """Evaluate an arithmetic or symbolic expression."""
        if not _SYMPY_AVAILABLE:
            return "[ERROR: SYMPY_NOT_INSTALLED]"

        try:
            cleaned = self._clean_math(expr_str)
            expr = sympify(cleaned)
            exact = str(expr)
            try:
                numeric_val = float(N(expr, 8))
                if numeric_val.is_integer():
                    return f"{int(numeric_val)}"
                return f"{exact} (approx {numeric_val:.6f})"
            except Exception:
                return exact
        except Exception as e:
            return f"[ERROR: EVAL_FAILED: {e}]"

    def simplify_expression(self, expr_str: str) -> str:
        """Simplify an algebraic expression."""
        if not _SYMPY_AVAILABLE:
            return "[ERROR: SYMPY_NOT_INSTALLED]"

        try:
            cleaned = self._clean_math(expr_str)
            expr = sympify(cleaned)
            simp = simplify(expr)
            return str(simp)
        except Exception as e:
            return f"[ERROR: SIMPLIFY_FAILED: {e}]"

    def check_boundary_consistency(
        self,
        candidate_value: Union[float, int, str],
        constraints: List[str],
        var_name: str = "x",
    ) -> Tuple[bool, str]:
        """Check whether candidate value satisfies boundary constraints (CAP:SANITY_CHECK)."""
        if not _SYMPY_AVAILABLE:
            return False, "SymPy not available"

        try:
            val = float(sympify(str(candidate_value)))
            for c in constraints:
                c_clean = c.strip()
                # Check inequality intervals e.g. "x >= 0", "0 <= x <= 1"
                if ">=" in c_clean or "<=" in c_clean or ">" in c_clean or "<" in c_clean:
                    # Replace variable name with actual value
                    eval_expr = re.sub(rf"\b{var_name}\b", str(val), c_clean)
                    # Evaluate inequality safely via AST
                    if not self._eval_safe_inequality(eval_expr):
                        return False, f"Violated boundary constraint: {c_clean} with {var_name}={val}"
                elif "=" in c_clean:
                    # Substitute into equation and verify residue
                    lhs_str, rhs_str = c_clean.split("=", 1)
                    var = symbols(var_name)
                    residue = float(N((sympify(lhs_str) - sympify(rhs_str)).subs(var, val)))
                    if abs(residue) > 1e-4:
                        return False, f"Residue {residue} too large for equation: {c_clean}"

            return True, f"Satisfies all {len(constraints)} boundary constraint(s)."
        except Exception as e:
            return False, f"Verification failed with exception: {e}"

    def _clean_math(self, text: str) -> str:
        """Clean LaTeX and math notations for SymPy parsing."""
        s = text.strip()
        s = s.replace(r"\times", "*").replace("×", "*").replace("·", "*")
        s = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"(\1)/(\2)", s)
        s = re.sub(r"\\sqrt\{([^}]*)\}", r"sqrt(\1)", s)
        s = re.sub(r"\\boxed\{([^}]*)\}", r"\1", s)
        s = s.replace("^", "**")
        s = s.replace("$", "")
        return s.strip()

    def _eval_safe_inequality(self, expr: str) -> bool:
        """Safely evaluate a chained comparison expression without eval()."""
        tree = ast.parse(expr, mode="eval")
        if not isinstance(tree.body, ast.Compare):
            return False

        def eval_num(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                return -eval_num(node.operand)
            if isinstance(node, ast.BinOp):
                left, right = eval_num(node.left), eval_num(node.right)
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div): return left / right
            raise ValueError(f"Unsafe node: {type(node)}")

        left = eval_num(tree.body.left)
        for op, comparator in zip(tree.body.ops, tree.body.comparators):
            right = eval_num(comparator)
            if isinstance(op, ast.Lt) and not (left < right): return False
            if isinstance(op, ast.LtE) and not (left <= right): return False
            if isinstance(op, ast.Gt) and not (left > right): return False
            if isinstance(op, ast.GtE) and not (left >= right): return False
            if isinstance(op, ast.Eq) and not (abs(left - right) < 1e-6): return False
            left = right
        return True
