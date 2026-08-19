"""Discover every place this project states its version."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from ..declaration import Declaration, is_ignored, usable
from ..discovery import read_text
from .changelog import Changelog, read_changelog
from .dunder import is_version_module, read_dunder
from .manifests import (
    read_cargo,
    read_chart,
    read_package_json,
    read_pyproject,
    read_setup_cfg,
)

__all__ = ["Changelog", "Collected", "GenericSource", "collect", "is_interesting"]

_BY_NAME = {
    "pyproject.toml": read_pyproject,
    "Cargo.toml": read_cargo,
    "package.json": read_package_json,
    "manifest.json": read_package_json,
    "setup.cfg": read_setup_cfg,
    "Chart.yaml": read_chart,
    "Chart.yml": read_chart,
}
_CHANGELOG_NAMES = ("CHANGELOG.md", "CHANGES.md", "HISTORY.md", "NEWS.md")


@dataclass(frozen=True, slots=True)
class GenericSource:
    """A user-supplied ``PATH:REGEX`` pair, for the formats not built in."""

    glob: str
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class Collected:
    manifests: tuple[Declaration, ...]
    changelog: Changelog | None


def is_interesting(path: Path, generic: Sequence[GenericSource] = ()) -> bool:
    """Report whether ``path`` could possibly state a version."""
    return (
        path.name in _BY_NAME
        or path.name in _CHANGELOG_NAMES
        or is_version_module(path)
        or any(fnmatch(path.as_posix(), source.glob) for source in generic)
    )


def _read_generic(
    path: Path, text: str, sources: Sequence[GenericSource]
) -> list[Declaration]:
    declarations: list[Declaration] = []
    for source in sources:
        if not fnmatch(path.as_posix(), source.glob):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            match = source.pattern.search(line)
            if match is None:
                continue
            version = match.groupdict().get("version")
            if version is None:
                version = match.group(1) if match.re.groups else match.group(0)
            if usable(version):
                declarations.append(
                    Declaration(
                        version=version,
                        path=path,
                        line=number,
                        detail=f"--source {source.glob}",
                    )
                )
                break
    return declarations


def collect(
    root: Path, files: Sequence[Path], *, generic: Sequence[GenericSource] = ()
) -> Collected:
    """Return every version declaration found across ``files``."""
    manifests: list[Declaration] = []
    changelog: Changelog | None = None

    for relative in files:
        if not is_interesting(relative, generic):
            continue
        text = read_text(root / relative)
        if text is None:
            continue

        if relative.name in _CHANGELOG_NAMES:
            found = read_changelog(relative, text)
            # A nested changelog never outranks the one at the top level.
            if changelog is None or len(relative.parts) == 1:
                changelog = found
            continue

        found_declarations: list[Declaration] = []
        reader = _BY_NAME.get(relative.name)
        if reader is not None:
            found_declarations += reader(relative, text)
        if is_version_module(relative):
            found_declarations += read_dunder(relative, text)
        found_declarations += _read_generic(relative, text, generic)

        manifests += [
            declaration
            for declaration in found_declarations
            if not is_ignored(text, declaration.line)
        ]

    return Collected(manifests=tuple(manifests), changelog=changelog)
