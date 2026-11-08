"""Run a model-written PAL program by interpreting its syntax tree, never with exec.

Only arithmetic, assignments, loops, conditions and a few pure built-ins are understood.
Anything else counts as a failed program, and failures are recorded rather than hidden.

`run_program(text, full=True)` also understands what MATH programs tend to use: functions,
while loops, containers and the pure parts of math, itertools and fractions. It still has no
exec, no file or network access, and no attribute access outside a fixed list.
"""

import ast
import fractions
import itertools
import math
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


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Function:
    def __init__(self, node):
        self.node = node


def _bounded_factorial(n):
    if n > 5000:
        raise _Unsupported("factorial too large")
    return math.factorial(n)


def _bounded_pow(base, power, modulus=None):
    if modulus is None and abs(power) > 4096:
        raise _Unsupported("power too large")
    return pow(base, power, modulus)


_MODULES = {
    "math": {
        **{name: getattr(math, name) for name in (
            "sqrt", "gcd", "lcm", "floor", "ceil", "pi", "e", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
            "radians", "degrees", "log", "log2", "log10", "exp", "hypot", "comb", "perm", "isqrt", "fabs",
        )},
        "factorial": _bounded_factorial,
        "pow": _bounded_pow,
    },
    "itertools": {name: getattr(itertools, name) for name in (
        "permutations", "combinations", "combinations_with_replacement", "product",
    )},
    "fractions": {"Fraction": fractions.Fraction},
}
_FULL_CALLS = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "float": float, "int": int, "len": len, "list": list, "map": map, "max": max, "min": min, "pow": _bounded_pow,
    "print": lambda *args: None, "range": range, "reversed": reversed, "round": round, "set": set, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "zip": zip,
}
_METHODS = {
    list: {"append", "extend", "pop", "sort", "remove", "insert", "index", "count", "reverse"},
    set: {"add", "discard", "remove", "update", "union", "intersection", "difference"},
    dict: {"get", "items", "keys", "values", "pop", "setdefault"},
    str: {"join", "count", "split"},
    float: {"is_integer"},
    int: {"bit_length"},
}
_FULL_BINARY = {
    **_BINARY, ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor, ast.RShift: operator.rshift,
}
_FULL_COMPARE = {**_COMPARE, ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
_MAX_LENGTH = 1_000_000


class _FullInterpreter(_Interpreter):
    limit = 5_000_000

    def tick(self):
        self.operations += 1
        if self.operations > self.limit:
            raise _Unsupported("too many operations")

    def binary(self, node):
        left, right = self.expression(node.left), self.expression(node.right)
        if isinstance(node.op, ast.Pow):
            return _bounded_pow(left, right)
        if isinstance(node.op, ast.LShift):
            if right > 4096:
                raise _Unsupported("shift too large")
            return left << right
        if isinstance(node.op, ast.Mult) and (isinstance(left, (list, str, tuple)) or isinstance(right, (list, str, tuple))):
            size, times = (left, right) if isinstance(left, (list, str, tuple)) else (right, left)
            if len(size) * times > _MAX_LENGTH:
                raise _Unsupported("sequence too long")
        if type(node.op) not in _FULL_BINARY:
            raise _Unsupported(type(node.op).__name__)
        return _FULL_BINARY[type(node.op)](left, right)

    def bind(self, target, value):
        if isinstance(target, ast.Name):
            self.names[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = list(value)
            if len(values) != len(target.elts):
                raise _Unsupported("unpacking")
            for item, part in zip(target.elts, values):
                self.bind(item, part)
        elif isinstance(target, ast.Subscript):
            self.expression(target.value)[self.expression(target.slice)] = value
        else:
            raise _Unsupported(type(target).__name__)

    def ticking(self, values):
        for value in values:
            self.tick()
            yield value

    def comprehension(self, generators, emit):
        if not generators:
            emit()
            return
        loop = generators[0]
        if loop.is_async:
            raise _Unsupported("comprehension")
        for value in self.ticking(self.expression(loop.iter)):
            self.bind(loop.target, value)
            if all(self.expression(test) for test in loop.ifs):
                self.comprehension(generators[1:], emit)

    def call(self, function, args, keywords):
        if isinstance(function, _Function):
            spec = function.node.args
            if keywords or spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs:
                raise _Unsupported("call signature")
            defaults = [self.expression(item) for item in spec.defaults]
            names = [item.arg for item in spec.args]
            bound = dict(zip(names[len(names) - len(defaults):], defaults)) | dict(zip(names, args))
            if len(args) > len(names) or set(names) - set(bound):
                raise TypeError("wrong arguments")
            outer, self.names = self.names, {**self.names, **bound}
            try:
                self.statements(function.node.body)
            except _Return as returned:
                return returned.value
            finally:
                self.names = outer
            return None
        if keywords and (function is not sorted or set(keywords) - {"reverse"}):
            raise _Unsupported("keyword argument")
        if function in (list, set, tuple, dict, sorted, sum, max, min, any, all) and args:
            args = [self.ticking(args[0]) if function is not dict else args[0], *args[1:]]
        if function is range:
            if len(range(*args)) > self.limit:
                raise _Unsupported("range too long")
        value = function(*args, **keywords)
        if function in _MODULES["itertools"].values() or function in (map, zip, enumerate, reversed):
            return self.ticking(value)
        return value

    def expression(self, node):
        self.tick()
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, float, str, bool, type(None)):
                raise _Unsupported("constant")
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.names:
                return self.names[node.id]
            if node.id in _FULL_CALLS:
                return _FULL_CALLS[node.id]
            raise _Unsupported(node.id)
        if isinstance(node, ast.BinOp):
            return self.binary(node)
        if isinstance(node, ast.UnaryOp):
            value = self.expression(node.operand)
            if isinstance(node.op, ast.Not):
                return not value
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            raise _Unsupported("unary")
        if isinstance(node, ast.BoolOp):
            result = None
            for item in node.values:
                result = self.expression(item)
                if bool(result) != isinstance(node.op, ast.And):
                    return result
            return result
        if isinstance(node, ast.IfExp):
            return self.expression(node.body if self.expression(node.test) else node.orelse)
        if isinstance(node, ast.Compare):
            left = self.expression(node.left)
            for op, item in zip(node.ops, node.comparators):
                right = self.expression(item)
                if type(op) not in _FULL_COMPARE or not _FULL_COMPARE[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.List):
            return [self.expression(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self.expression(item) for item in node.elts)
        if isinstance(node, ast.Set):
            return {self.expression(item) for item in node.elts}
        if isinstance(node, ast.Dict):
            if None in node.keys:
                raise _Unsupported("dict unpacking")
            return {self.expression(key): self.expression(item) for key, item in zip(node.keys, node.values)}
        if isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            values = []
            self.comprehension(node.generators, lambda: values.append(self.expression(node.elt)))
            return set(values) if isinstance(node, ast.SetComp) else values
        if isinstance(node, ast.DictComp):
            values = {}
            self.comprehension(node.generators, lambda: values.update({self.expression(node.key): self.expression(node.value)}))
            return values
        if isinstance(node, ast.Slice):
            parts = (node.lower, node.upper, node.step)
            return slice(*[self.expression(item) if item else None for item in parts])
        if isinstance(node, ast.Subscript):
            return self.expression(node.value)[self.expression(node.slice)]
        if isinstance(node, ast.JoinedStr):
            raise _Unsupported("f-string")
        if isinstance(node, ast.Attribute):
            return self.attribute(node)
        if isinstance(node, ast.Call):
            if any(item.arg is None for item in node.keywords) or any(isinstance(arg, ast.Starred) for arg in node.args):
                raise _Unsupported("unpacked arguments")
            function = self.expression(node.func)
            if not callable(function) and not isinstance(function, _Function):
                raise _Unsupported("call")
            args = [self.expression(arg) for arg in node.args]
            return self.call(function, args, {item.arg: self.expression(item.value) for item in node.keywords})
        raise _Unsupported(type(node).__name__)

    def attribute(self, node):
        owner = self.expression(node.value)
        if isinstance(owner, _Module):
            if node.attr not in owner.members:
                raise _Unsupported(node.attr)
            return owner.members[node.attr]
        if node.attr not in _METHODS.get(type(owner), ()):
            raise _Unsupported(node.attr)
        return getattr(owner, node.attr)

    def imports(self, node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _MODULES:
                    raise _Unsupported(alias.name)
                self.names[alias.asname or alias.name] = _Module(_MODULES[alias.name])
            return
        if node.module not in _MODULES:
            raise _Unsupported(str(node.module))
        for alias in node.names:
            if alias.name not in _MODULES[node.module]:
                raise _Unsupported(alias.name)
            self.names[alias.asname or alias.name] = _MODULES[node.module][alias.name]

    def statements(self, body):
        for node in body:
            self.tick()
            if isinstance(node, ast.Assign):
                value = self.expression(node.value)
                for target in node.targets:
                    self.bind(target, value)
            elif isinstance(node, ast.AugAssign):
                self.bind(node.target, self.binary(ast.BinOp(left=_read(node.target), op=node.op, right=node.value)))
            elif isinstance(node, ast.For):
                for value in self.ticking(self.expression(node.iter)):
                    self.bind(node.target, value)
                    try:
                        self.statements(node.body)
                    except _Break:
                        break
                    except _Continue:
                        continue
                else:
                    self.statements(node.orelse)
            elif isinstance(node, ast.While):
                while self.expression(node.test):
                    self.tick()
                    try:
                        self.statements(node.body)
                    except _Break:
                        break
                    except _Continue:
                        continue
                else:
                    self.statements(node.orelse)
            elif isinstance(node, ast.If):
                self.statements(node.body if self.expression(node.test) else node.orelse)
            elif isinstance(node, ast.FunctionDef):
                if node.decorator_list:
                    raise _Unsupported("decorator")
                self.names[node.name] = _Function(node)
            elif isinstance(node, ast.Return):
                raise _Return(self.expression(node.value) if node.value else None)
            elif isinstance(node, ast.Break):
                raise _Break
            elif isinstance(node, ast.Continue):
                raise _Continue
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.imports(node)
            elif isinstance(node, ast.Expr):
                self.expression(node.value)
            elif not isinstance(node, ast.Pass):
                raise _Unsupported(type(node).__name__)


class _Module:
    def __init__(self, members):
        self.members = members


def _read(target):
    """Turn an assignment target into the expression that reads it, for `x += 1` and `a[i] += 1`."""
    if isinstance(target, ast.Name):
        return ast.Name(id=target.id, ctx=ast.Load())
    if isinstance(target, ast.Subscript):
        return ast.Subscript(value=target.value, slice=target.slice, ctx=ast.Load())
    raise _Unsupported(type(target).__name__)


def refusal(text):
    """Say why the full interpreter gave no number for a program, or None if it gave one."""
    match = _FENCE.search(text)
    source = match[1] if match else text
    try:
        interpreter = _FullInterpreter()
        interpreter.statements(ast.parse(source).body)
        result = interpreter.names["result"]
    except _Unsupported as error:
        return f"unsupported: {error}"
    except KeyError:
        return "no result"
    except (SyntaxError, ArithmeticError, TypeError, ValueError, IndexError, AttributeError, RecursionError,
            _Return, _Break, _Continue) as error:
        return type(error).__name__
    return None if isinstance(result, (int, float, fractions.Fraction)) and not isinstance(result, bool) else "non-numeric result"


def run_program(text, full=False):
    """Return the program's numeric `result`, or None if it can't be determined."""
    match = _FENCE.search(text)
    source = match[1] if match else text
    errors = (_Unsupported, SyntaxError, KeyError, ArithmeticError, TypeError, ValueError)
    try:
        interpreter = _FullInterpreter() if full else _Interpreter()
        interpreter.statements(ast.parse(source).body)
        result = interpreter.names["result"]
    except errors:
        return None
    except (IndexError, AttributeError, RecursionError, _Return, _Break, _Continue):
        return None
    if type(result) not in (int, float) and not (full and type(result) is fractions.Fraction):
        return None
    return float(result)
