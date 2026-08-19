"""One place where a project states its version."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IGNORE_MARKER = "check-version-consistency: ignore"

# Loose on purpose: a project is free to use dates, four segments or a build
# suffix. This only has to reject the things that are not versions at all,
# such as the "attr: mypkg.__version__" spelling of a dynamic version.
VERSION_LIKE = re.compile(r"^\d+(?:\.\d+)*(?:[-+._][0-9A-Za-z.\-+]*)?$")

# Values that mean "this is filled in at release time", not a real version.
PLACEHOLDERS = ("0.0.0",)


@dataclass(frozen=True, slots=True)
class Declaration:
    """A version, where it was found, and what stated it."""

    version: str
    path: Path
    line: int
    detail: str
    is_changelog: bool = False


def is_placeholder(version: str) -> bool:
    return any(
        version == placeholder or version.startswith(f"{placeholder}-")
        for placeholder in PLACEHOLDERS
    )


def usable(version: object) -> bool:
    """Report whether a value is a version this tool should compare."""
    return (
        isinstance(version, str)
        and bool(VERSION_LIKE.match(version))
        and not is_placeholder(version)
    )


def locate_line(text: str, key: str, value: str) -> int:
    """Find the line a parsed value came from.

    ``tomllib`` and ``json`` hand back values without telling you where they
    were, and a finding you cannot click on is half a finding. Re-reading the
    raw text is cheap and, for a key/value pair on one line, exact.
    """
    lines = text.splitlines()
    for number, source in enumerate(lines, start=1):
        if key in source and value in source:
            return number
    for number, source in enumerate(lines, start=1):
        if value in source:
            return number
    return 1


def is_ignored(text: str, line: int) -> bool:
    lines = text.splitlines()
    return 0 < line <= len(lines) and IGNORE_MARKER in lines[line - 1]
