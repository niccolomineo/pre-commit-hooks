"""``__version__`` in a Python source, read with ``ast``."""

from __future__ import annotations

import ast
from pathlib import Path

from ..declaration import Declaration, usable

FILENAMES = ("__init__.py", "version.py", "_version.py", "__version__.py")


def is_version_module(path: Path) -> bool:
    return path.name in FILENAMES


def _assigned_names(node: ast.stmt) -> list[str]:
    if isinstance(node, ast.Assign):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def read_dunder(path: Path, text: str) -> list[Declaration]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    # Module level only: a __version__ nested in a function or a class is not
    # the package's version.
    for node in tree.body:
        if "__version__" not in _assigned_names(node):
            continue
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Constant) or not usable(value.value):
            continue
        return [
            Declaration(
                version=value.value,
                path=path,
                line=node.lineno,
                detail="__version__",
            )
        ]
    return []
