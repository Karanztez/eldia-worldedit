"""Safe AST-based math expression evaluator for WorldEdit //calc, //gen, //deform, and =masks."""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any


class ExpressionError(ValueError):
    """Raised when a math expression is malformed or contains disallowed syntax."""


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


def _fade(t: float) -> float:
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _hash3(ix: int, iy: int, iz: int) -> float:
    n = (ix * 374761393 + iy * 668265263 + iz * 2147483647) & 0x7FFFFFFF
    n = (n ^ (n >> 13)) * 1274126177
    n = (n ^ (n >> 16)) & 0x7FFFFFFF
    return (n / 0x7FFFFFFF) * 2.0 - 1.0


def _noise3(x: float, y: float = 0.0, z: float = 0.0) -> float:
    """Deterministic 3D smooth value noise in [-1, 1]."""
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    ux, uy, uz = _fade(fx), _fade(fy), _fade(fz)

    c000 = _hash3(ix, iy, iz)
    c100 = _hash3(ix + 1, iy, iz)
    c010 = _hash3(ix, iy + 1, iz)
    c110 = _hash3(ix + 1, iy + 1, iz)
    c001 = _hash3(ix, iy, iz + 1)
    c101 = _hash3(ix + 1, iy, iz + 1)
    c011 = _hash3(ix, iy + 1, iz + 1)
    c111 = _hash3(ix + 1, iy + 1, iz + 1)

    x00 = _lerp(c000, c100, ux)
    x10 = _lerp(c010, c110, ux)
    x01 = _lerp(c001, c101, ux)
    x11 = _lerp(c011, c111, ux)
    y0 = _lerp(x00, x10, uy)
    y1 = _lerp(x01, x11, uy)
    return _lerp(y0, y1, uz)


_SAFE_FUNCS: dict[str, Any] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "sqrt": lambda v: math.sqrt(max(0.0, float(v))),
    "abs": abs,
    "floor": lambda v: float(math.floor(v)),
    "ceil": lambda v: float(math.ceil(v)),
    "round": lambda v, n=0: float(round(v, int(n))),
    "min": min,
    "max": max,
    "log": lambda v: math.log(max(1e-12, float(v))),
    "ln": lambda v: math.log(max(1e-12, float(v))),
    "log10": lambda v: math.log10(max(1e-12, float(v))),
    "exp": math.exp,
    "pow": math.pow,
    "clamp": lambda v, lo, hi: max(lo, min(hi, v)),
    "sign": lambda v: 1.0 if v > 0 else (-1.0 if v < 0 else 0.0),
    "hypot": math.hypot,
    "noise": _noise3,
    "rint": lambda v: float(round(v)),
}

_SAFE_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "true": 1.0,
    "false": 0.0,
}


def _rewrite_ternary(expr: str) -> str:
    """Convert C/WorldEdit 'cond ? a : b' into Python '(a if cond else b)'."""
    q_idx = _find_top_level(expr, "?")
    if q_idx == -1:
        return expr
    cond = expr[:q_idx].strip()
    rest = expr[q_idx + 1 :]
    c_idx = _find_matching_colon(rest)
    if c_idx == -1:
        raise ExpressionError("Ternary '?' missing matching ':'.")
    true_branch = _rewrite_ternary(rest[:c_idx].strip())
    false_branch = _rewrite_ternary(rest[c_idx + 1 :].strip())
    return f"(({true_branch}) if ({_rewrite_ternary(cond)}) else ({false_branch}))"


def _find_top_level(s: str, ch: str) -> int:
    depth = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == ch and depth == 0:
            return i
    return -1


def _find_matching_colon(s: str) -> int:
    depth = 0
    nested_q = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            if c == "?":
                nested_q += 1
            elif c == ":":
                if nested_q == 0:
                    return i
                nested_q -= 1
    return -1


def _preprocess(expr: str) -> str:
    text = expr.strip()
    if not text:
        raise ExpressionError("Empty expression.")
    text = _rewrite_ternary(text)
    text = text.replace("^", "**")
    text = text.replace("&&", " and ")
    text = text.replace("||", " or ")
    # Convert unary '!' (not '!=') to ' not '
    text = re.sub(r"!(?!=)", " not ", text)
    return text.strip()


_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def _validate_ast(tree: ast.AST) -> None:
    for count, node in enumerate(ast.walk(tree), start=1):
        if count > 500:
            raise ExpressionError("Expression is too complex (exceeds 500 AST nodes).")
        if not isinstance(node, _ALLOWED_NODES):
            raise ExpressionError(f"Disallowed syntax in expression: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCS:
                func_name = getattr(node.func, "id", type(node.func).__name__)
                raise ExpressionError(f"Unknown or disallowed function '{func_name}'.")
            if node.keywords:
                raise ExpressionError("Keyword arguments are not supported in expressions.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
            raise ExpressionError("Only numeric constants are allowed in expressions.")


def _eval_node(node: ast.AST, env: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in env:
            return float(env[node.id])
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise ExpressionError(f"Unknown variable '{node.id}'.")
    if isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return +val
        if isinstance(node.op, ast.USub):
            return -val
        if isinstance(node.op, ast.Not):
            return 1.0 if val == 0.0 else 0.0
        raise ExpressionError("Unsupported unary operator.")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return 0.0 if right == 0.0 else left / right
        if isinstance(node.op, ast.FloorDiv):
            return 0.0 if right == 0.0 else float(left // right)
        if isinstance(node.op, ast.Mod):
            return 0.0 if right == 0.0 else left % right
        if isinstance(node.op, ast.Pow):
            try:
                return float(left**right)
            except (OverflowError, ZeroDivisionError, ValueError):
                return 0.0
        raise ExpressionError("Unsupported binary operator.")
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for val_node in node.values:
                if _eval_node(val_node, env) == 0.0:
                    return 0.0
            return 1.0
        if isinstance(node.op, ast.Or):
            for val_node in node.values:
                if _eval_node(val_node, env) != 0.0:
                    return 1.0
            return 0.0
        raise ExpressionError("Unsupported boolean operator.")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, env)
        for op, comp in zip(node.ops, node.comparators, strict=True):
            right = _eval_node(comp, env)
            ok = False
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            if not ok:
                return 0.0
            left = right
        return 1.0
    if isinstance(node, ast.IfExp):
        cond = _eval_node(node.test, env)
        return _eval_node(node.body if cond != 0.0 else node.orelse, env)
    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)
        fn = _SAFE_FUNCS[node.func.id]
        args = [_eval_node(arg, env) for arg in node.args]
        try:
            return float(fn(*args))
        except (ValueError, TypeError, OverflowError) as exc:
            raise ExpressionError(f"Math evaluation error in '{node.func.id}': {exc}") from exc
    raise ExpressionError(f"Unsupported AST node: {type(node).__name__}")


@dataclass(frozen=True)
class CompiledExpression:
    """Pre-parsed, validated math expression."""

    source: str
    tree: ast.Expression

    def evaluate(self, variables: dict[str, float] | None = None) -> float:
        env = variables or {}
        return _eval_node(self.tree, env)


def compile_expression(expr: str) -> CompiledExpression:
    """Parse and validate a WorldEdit math expression."""
    processed = _preprocess(expr)
    try:
        parsed = ast.parse(processed, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Invalid expression syntax '{expr}': {exc.msg}") from exc
    _validate_ast(parsed)
    return CompiledExpression(source=expr, tree=parsed)


def evaluate_expression(expr: str, variables: dict[str, float] | None = None) -> float:
    """Compile and evaluate a math expression once."""
    return compile_expression(expr).evaluate(variables)
