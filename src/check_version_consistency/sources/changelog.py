"""The topmost released entry of a changelog.

Both Keep a Changelog spellings are understood::

    ## [1.4.0] - 2026-08-18
    ## 1.4.0 - 2026-08-18

An ``## [Unreleased]`` section above the first released entry is not a version;
it is the signal that a release is in progress, which the lenient rule uses to
allow the changelog to sit one release behind the manifests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..declaration import Declaration, usable

_HEADING = re.compile(r"^\s{0,3}##\s+(?P<body>.+?)\s*$")
_VERSION = re.compile(r"^\[?(?P<version>[^\]\s]+)\]?")
_UNRELEASED = re.compile(r"^\[?unreleased\]?", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Changelog:
    declaration: Declaration | None
    has_unreleased: bool


def read_changelog(path: Path, text: str) -> Changelog:
    has_unreleased = False
    inside_code_fence = False
    for number, source in enumerate(text.splitlines(), start=1):
        if source.lstrip().startswith(("```", "~~~")):
            inside_code_fence = not inside_code_fence
            continue
        if inside_code_fence:
            continue
        heading = _HEADING.match(source)
        if heading is None:
            continue
        body = heading["body"]
        if _UNRELEASED.match(body):
            has_unreleased = True
            continue
        match = _VERSION.match(body)
        if match is None:
            continue
        version = match["version"].removeprefix("v")
        if not usable(version):
            continue
        declaration = Declaration(
            version=version,
            path=path,
            line=number,
            detail=f"## {body}",
            is_changelog=True,
        )
        return Changelog(declaration=declaration, has_unreleased=has_unreleased)
    return Changelog(declaration=None, has_unreleased=has_unreleased)
