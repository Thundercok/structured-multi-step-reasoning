"""Run a model-written PAL program by interpreting its syntax tree, never with exec.

Only arithmetic, assignments, loops, conditions and a few pure built-ins are understood.
Anything else counts as a failed program, and failures are recorded rather than hidden.
"""

import ast
import operator
import re

_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}
_COMPARE = {
    ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
}
_MAX_OPERATIONS = 100_000


def _bounded_range(*args):
    span = range(*args)
    if len(span) > _MAX_OPERATIONS:
        raise _Unsupported("range too long")
    return list(span)


_CALLS = {
    "abs": abs, "float": float, "int": int, "len": len, "max": max, "min": min,
    "range": _bounded_range, "round": round, "sum": sum,
}
_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)


class _Unsupported(Exception):
    pass


class _Interpreter:
    def __init__(self):
        self.names, self.operations = {}, 0

    def tick(self):
        self.operations += 1
        if self.operations > _MAX_OPERATIONS:
            raise _Unsupported("too many operations")

    def number(self, node):
        """Operands must be numbers, so `[0] * 10**9` can't allocate a huge list."""
        value = self.expression(node)
        if type(value) not in (int, float):
            raise _Unsupported("non-numeric operand")
        return value

    def expression(self, node):
        self.tick()
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](self.number(node.left), self.number(node.right))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            base, power = self.number(node.left), self.number(node.right)
            if abs(power) > 64:
                raise _Unsupported("power too large")
            return base**power
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = self.expression(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.expression(item) for item in node.elts]
        if isinstance(node, (ast.GeneratorExp, ast.ListComp)) and len(node.generators) == 1:
            loop = node.generators[0]
            if not isinstance(loop.target, ast.Name) or loop.ifs or loop.is_async:
                raise _Unsupported("comprehension")
            values = []
            for value in self.expression(loop.iter):
                self.names[loop.target.id] = value
                values.append(self.expression(node.elt))
            return values
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE:
            return _COMPARE[type(node.ops[0])](self.expression(node.left), self.expression(node.comparators[0]))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _CALLS
                and not node.keywords):
            return _CALLS[node.func.id](*[self.expression(arg) for arg in node.args])
        raise _Unsupported(type(node).__name__)

    def statements(self, body):
        for node in body:
            self.tick()
            if isinstance(node, ast.Assign) and all(isinstance(target, ast.Name) for target in node.targets):
                value = self.expression(node.value)
                for target in node.targets:
                    self.names[target.id] = value
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and type(node.op) in _BINARY:
                self.names[node.target.id] = _BINARY[type(node.op)](
                    self.expression(node.target), self.expression(node.value))
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name) and not node.orelse:
                for value in self.expression(node.iter):
                    self.names[node.target.id] = value
                    self.statements(node.body)
            elif isinstance(node, ast.If):
                self.statements(node.body if self.expression(node.test) else node.orelse)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                pass
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) \
                    and getattr(node.value.func, "id", None) == "print":
                pass
            else:
                raise _Unsupported(type(node).__name__)


def run_program(text):
    """Return the program's numeric `result`, or None if it can't be determined."""
    match = _FENCE.search(text)
    source = match[1] if match else text
    try:
        interpreter = _Interpreter()
        interpreter.statements(ast.parse(source).body)
        result = interpreter.names["result"]
    except (_Unsupported, SyntaxError, KeyError, ArithmeticError, TypeError, ValueError):
        return None
    if type(result) not in (int, float):
        return None
    return float(result)
