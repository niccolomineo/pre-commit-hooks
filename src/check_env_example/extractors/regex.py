"""Pattern tables for the languages that are matched rather than parsed."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from fnmatch import fnmatch
from pathlib import Path

_NAME = r"[A-Za-z_][A-Za-z0-9_]*"

_JAVASCRIPT = (
    rf"process\.env\.(?P<var>{_NAME})",
    rf"process\.env\[\s*['\"](?P<var>{_NAME})['\"]\s*\]",
    rf"import\.meta\.env\.(?P<var>{_NAME})",
    rf"Deno\.env\.get\(\s*['\"](?P<var>{_NAME})['\"]",
    rf"Bun\.env\.(?P<var>{_NAME})",
)
_GO = (rf"os\.(?:Getenv|LookupEnv)\(\s*\"(?P<var>{_NAME})\"",)
_RUST = (rf"env::var(?:_os)?\(\s*\"(?P<var>{_NAME})\"",)
_RUBY = (
    rf"ENV\.fetch\(\s*['\"](?P<var>{_NAME})['\"]",
    rf"ENV\[\s*['\"](?P<var>{_NAME})['\"]\s*\]",
)
_PHP = (
    rf"getenv\(\s*['\"](?P<var>{_NAME})['\"]",
    rf"\$_ENV\[\s*['\"](?P<var>{_NAME})['\"]\s*\]",
)
# Only a build argument without a default has to be supplied from the outside.
_DOCKERFILE = (rf"^\s*ARG\s+(?P<var>{_NAME})\s*$",)


def _compile(patterns: Sequence[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


_BY_SUFFIX: dict[str, tuple[re.Pattern[str], ...]] = {
    suffix: _compile(_JAVASCRIPT)
    for suffix in (
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".mts",
        ".cts",
        ".vue",
        ".svelte",
        ".astro",
    )
} | {
    ".go": _compile(_GO),
    ".rs": _compile(_RUST),
    ".rb": _compile(_RUBY),
    ".php": _compile(_PHP),
}

_BY_GLOB: tuple[tuple[tuple[str, ...], tuple[re.Pattern[str], ...]], ...] = (
    (("Dockerfile*", "*.Dockerfile", "Containerfile*"), _compile(_DOCKERFILE)),
)

# A line that opens with one of these is a comment in every language we scan.
# Cheap, and it removes the commented-out-code false positive almost entirely.
_COMMENT_PREFIXES = ("//", "#", "*", "/*", "<!--", "--")


def patterns_for(path: Path) -> tuple[re.Pattern[str], ...]:
    """Return the built-in patterns that apply to ``path``."""
    by_suffix = _BY_SUFFIX.get(path.suffix.lower())
    if by_suffix is not None:
        return by_suffix
    for globs, patterns in _BY_GLOB:
        if any(fnmatch(path.name, glob) for glob in globs):
            return patterns
    return ()


def extract_with_patterns(
    lines: Sequence[str], patterns: Sequence[re.Pattern[str]]
) -> Iterator[tuple[str, int]]:
    """Yield ``(variable, line)`` for every match outside a comment line."""
    for number, source in enumerate(lines, start=1):
        if source.lstrip().startswith(_COMMENT_PREFIXES):
            continue
        for pattern in patterns:
            for match in pattern.finditer(source):
                yield match["var"], number
