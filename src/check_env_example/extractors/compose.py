"""Find environment reads in Compose files.

Compose takes a variable from the host in two different ways, and both count:
``${VAR}`` interpolated anywhere in the file, and a bare name listed under
``environment:`` or ``args:``, which means "pass mine through". The second form
carries no ``$`` at all, so pattern matching alone would walk straight past it.

There is no YAML parser in the standard library, so the block is tracked by
indentation. That is enough: the two keys we care about hold a flat list or a
flat mapping, never a nested structure.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from fnmatch import fnmatch
from pathlib import Path

_GLOBS = (
    "compose*.yaml",
    "compose*.yml",
    "docker-compose*.yaml",
    "docker-compose*.yml",
)

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
# $${VAR} is an escape: it reaches the container literally and never touches
# the host environment.
_INTERPOLATION = re.compile(rf"(?<!\$)\$\{{(?P<var>{_NAME})\s*[}}:?+\-]")
_BLOCK_START = re.compile(r"^(?P<indent>\s*)(?:environment|args)\s*:\s*(?P<inline>.*)$")
_LIST_ITEM = re.compile(r"^\s*-\s*(?P<body>\S.*?)\s*$")
_MAPPING_ITEM = re.compile(rf"^\s*(?P<key>{_NAME})\s*:\s*(?P<value>.*?)\s*$")
_NAME_ONLY = re.compile(rf"^{_NAME}$")


def is_compose(path: Path) -> bool:
    return any(fnmatch(path.name, glob) for glob in _GLOBS)


def _pass_through(source: str) -> str | None:
    """Return the variable a line hands over from the host, if it does."""
    item = _LIST_ITEM.match(source)
    if item is not None:
        # "- FOO" passes the host value on; "- FOO=bar" sets its own.
        body = item["body"].split("#")[0].strip().strip("\"'")
        return body if _NAME_ONLY.match(body) else None
    mapping = _MAPPING_ITEM.match(source)
    if mapping is not None and not mapping["value"].split("#")[0].strip():
        # "FOO:" with no value is the mapping spelling of the same thing.
        return mapping["key"]
    return None


def extract_compose(lines: Sequence[str]) -> Iterator[tuple[str, int]]:
    """Yield ``(variable, line)`` for every host variable the file consumes."""
    block_indent: int | None = None
    for number, source in enumerate(lines, start=1):
        stripped = source.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(source) - len(source.lstrip())

        if block_indent is not None and indent <= block_indent:
            block_indent = None

        start = _BLOCK_START.match(source)
        if start is not None and not start["inline"].strip():
            block_indent = len(start["indent"])
        elif block_indent is not None:
            name = _pass_through(source)
            if name is not None:
                yield name, number

        for match in _INTERPOLATION.finditer(source):
            yield match["var"], number
