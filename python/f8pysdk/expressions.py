"""Typed, dependency-free expression values and configurable language validation.

NumPy bindings belong to callers. Dynamic attributes here are JSON keys supplied
by graph authors, never reflection over application objects.
"""
from __future__ import annotations

import ast
import math
from collections.abc import Iterator, Mapping, Sequence, Set
from types import CodeType
from typing import cast

from .expr_policy import EXPRESSION_AST_NODES, numpy_attribute_allowed

MATH_FUNCTIONS = frozenset({
    "acos", "asin", "atan", "atan2", "ceil", "cos", "exp", "floor", "log", "log10", "sin", "sqrt", "tan",
})


def sigmoid(value: object) -> float:
    numeric = float(cast(float | int | str, value))
    if numeric >= 0:
        return 1.0 / (1.0 + math.exp(-numeric))
    exponential = math.exp(numeric)
    return exponential / (1.0 + exponential)


GLOBAL_FUNCTIONS: dict[str, object] = {
    "abs": abs, "all": all, "any": any, "float": float, "int": int, "len": len,
    "max": max, "min": min, "range": range, "round": round, "sigmoid": sigmoid,
    "sorted": sorted, "sum": sum,
}


def is_identifier(name: str) -> bool:
    return bool(name) and name.isidentifier()


def normalize_expr_code(value: object) -> str:
    text = "" if value is None else str(value)
    return " ".join(part.strip() for part in text.splitlines() if part.strip()).strip()


class JsonRef:
    __slots__ = ("_value",)

    def __init__(self, value: Mapping[object, object] | Sequence[object]) -> None:
        self._value = value

    def __getattr__(self, name: str) -> object:
        if name and not name.startswith("_") and isinstance(self._value, Mapping) and name in self._value:
            return wrap_value(self._value[name])
        raise AttributeError(name)

    def __getitem__(self, key: object) -> object:
        if isinstance(self._value, Mapping):
            if isinstance(key, str) and key.startswith("_"):
                raise KeyError(key)
            return wrap_value(self._value[key])
        if isinstance(key, bool) or not isinstance(key, (int, slice)):
            raise TypeError("sequence index must be an integer or slice")
        return wrap_value(self._value[key])

    def __iter__(self) -> Iterator[object]:
        if isinstance(self._value, Mapping):
            yield from self._value
        else:
            for value in self._value:
                yield wrap_value(value)

    def __len__(self) -> int:
        return len(self._value)

    def unwrap(self) -> object:
        return unwrap_value(self._value)


def wrap_value(value: object) -> object:
    if isinstance(value, Mapping):
        return JsonRef(cast(Mapping[object, object], value))
    if isinstance(value, (list, tuple)):
        return JsonRef(cast(Sequence[object], value))
    return value


def unwrap_value(value: object) -> object:
    if isinstance(value, JsonRef):
        return value.unwrap()
    if isinstance(value, Mapping):
        return {str(key): unwrap_value(item) for key, item in cast(Mapping[object, object], value).items()}
    if isinstance(value, list):
        return [unwrap_value(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(unwrap_value(item) for item in cast(tuple[object, ...], value))
    return value


class ExpressionValidator(ast.NodeVisitor):
    def __init__(self, *, functions: Set[str], math_functions: Set[str] = MATH_FUNCTIONS,
                 allow_numpy: bool = False) -> None:
        self._functions = functions
        self._math_functions = math_functions
        self._allow_numpy = allow_numpy
        self._errors: list[str] = []

    def validate(self, expression: str) -> tuple[ast.Expression | None, str | None]:
        self._errors.clear()
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            return None, f"syntax error: {exc.msg}"
        self.visit(tree)
        return (None, "; ".join(self._errors[:3])) if self._errors else (tree, None)

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, EXPRESSION_AST_NODES):
            self._errors.append(f"disallowed syntax: {type(node).__name__}")
            return
        super().generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self._errors.append("private/dunder attribute access is not allowed")
            return
        if not numpy_attribute_allowed(node):
            self._errors.append("numpy member is not allowed in numeric expressions")
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in self._functions:
                self._errors.append(f"call not allowed: {node.func.id}")
                return
        elif isinstance(node.func, ast.Attribute):
            base = node.func.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name) and base.id == "math" and isinstance(node.func.value, ast.Name):
                if node.func.attr not in self._math_functions:
                    self._errors.append(f"math call not allowed: math.{node.func.attr}")
                    return
            elif isinstance(base, ast.Name) and base.id in ("np", "numpy"):
                if not self._allow_numpy:
                    self._errors.append("numpy calls are disabled")
                    return
            else:
                self._errors.append("call target not allowed")
                return
        else:
            self._errors.append("call target not allowed")
            return
        self.generic_visit(node)


def compile_expression(expression: str, *, functions: Set[str], math_functions: Set[str] = MATH_FUNCTIONS,
                       allow_numpy: bool = False) -> tuple[CodeType | None, str | None]:
    tree, error = ExpressionValidator(functions=functions, math_functions=math_functions,
                                      allow_numpy=allow_numpy).validate(expression)
    if tree is None:
        return None, error
    try:
        return compile(tree, "<f8.expression>", "eval"), None
    except (TypeError, ValueError) as exc:
        return None, f"compile error: {exc}"


def evaluate_expression(code: CodeType, *, names: Mapping[str, object], functions: Mapping[str, object],
                        numpy_module: object | None = None) -> object:
    globals_: dict[str, object] = {"__builtins__": {}, "math": math, **functions}
    if numpy_module is not None:
        globals_.update(np=numpy_module, numpy=numpy_module)
    return cast(object, eval(code, globals_, dict(names)))  # noqa: S307
