"""Turn a source file into the list of environment variables it reads."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .compose import extract_compose, is_compose
from .python_ast import extract_python
from .regex import extract_with_patterns, patterns_for

__all__ = ["IGNORE_MARKER", "Reference", "extract", "is_scannable"]

IGNORE_MARKER = "check-env-example: ignore"

ExtraPatterns = Mapping[str, Sequence[re.Pattern[str]]]


@dataclass(frozen=True, slots=True)
class Reference:
    """One place where the code reads an environment variable."""

    var: str
    path: Path
    line: int


def is_scannable(path: Path, extra_patterns: ExtraPatterns | None = None) -> bool:
    """Report whether anything at all knows how to read ``path``."""
    if path.suffix == ".py" or is_compose(path) or patterns_for(path):
        return True
    return bool(extra_patterns) and path.suffix in extra_patterns


def extract(
    path: Path, text: str, extra_patterns: ExtraPatterns | None = None
) -> list[Reference]:
    """Return every environment read in ``text``, deduplicated per line."""
    lines = text.splitlines()
    found: list[tuple[str, int]] = []
    if path.suffix == ".py":
        found.extend(extract_python(text))
    elif is_compose(path):
        found.extend(extract_compose(lines))
    patterns = tuple(patterns_for(path))
    if extra_patterns:
        patterns += tuple(extra_patterns.get(path.suffix, ()))
    if patterns:
        found.extend(extract_with_patterns(lines, patterns))

    references: list[Reference] = []
    seen: set[tuple[str, int]] = set()
    for var, line in found:
        if (var, line) in seen:
            continue
        seen.add((var, line))
        source = lines[line - 1] if 0 < line <= len(lines) else ""
        if IGNORE_MARKER in source:
            continue
        references.append(Reference(var=var, path=path, line=line))
    references.sort(key=lambda reference: (reference.line, reference.var))
    return references
