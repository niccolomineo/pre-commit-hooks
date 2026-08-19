"""Find environment reads in Python sources through the standard ``ast``.

Parsing rather than pattern matching costs nothing here and buys precision:
commented-out code and strings that merely look like an environment read never
produce a finding, and the reported line is the real one.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

_ENVIRON_NAMES = frozenset({"os.environ", "environ"})
_GETENV_NAMES = frozenset({"os.getenv", "getenv"})
_ENVIRON_METHODS = frozenset({"get", "setdefault", "pop"})


def _dotted_name(node: ast.expr) -> str | None:
    """Render an attribute chain, so ``os.environ`` comes back as a string."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _constant_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_python(text: str) -> Iterator[tuple[str, int]]:
    """Yield ``(variable, line)`` for every environment read in ``text``."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        # A file that does not parse is not this hook's problem to report;
        # check-ast and the language's own linter already cover it.
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            if _dotted_name(node.value) in _ENVIRON_NAMES:
                name = _constant_str(node.slice)
                if name:
                    yield name, node.lineno
        elif isinstance(node, ast.Call):
            name = _constant_str(node.args[0]) if node.args else None
            if not name:
                continue
            if _dotted_name(node.func) in _GETENV_NAMES or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _ENVIRON_METHODS
                and _dotted_name(node.func.value) in _ENVIRON_NAMES
            ):
                yield name, node.lineno
