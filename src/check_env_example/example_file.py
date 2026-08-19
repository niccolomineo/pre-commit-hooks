"""Parse the ``.env.example`` file that documents the project's variables."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .extractors import IGNORE_MARKER

CANDIDATE_NAMES = (".env.example", ".env.sample", ".env.template", "env.example")

_ENTRY = re.compile(r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=")


@dataclass(frozen=True, slots=True)
class Entry:
    """A documented variable, and whether it opts out of the unused check."""

    key: str
    line: int
    ignored: bool


@dataclass(frozen=True, slots=True)
class Duplicate:
    key: str
    line: int
    first_line: int


@dataclass(frozen=True, slots=True)
class ExampleFile:
    path: Path
    entries: tuple[Entry, ...]
    duplicates: tuple[Duplicate, ...]

    def by_key(self) -> dict[str, Entry]:
        return {entry.key: entry for entry in self.entries}


def discover(root: Path) -> Path | None:
    """Return the first conventional example file present in ``root``."""
    for name in CANDIDATE_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def parse(path: Path, text: str) -> ExampleFile:
    """Read ``KEY=value`` lines, tolerating ``export``, comments and blanks."""
    entries: list[Entry] = []
    duplicates: list[Duplicate] = []
    first_seen: dict[str, int] = {}
    for number, source in enumerate(text.splitlines(), start=1):
        if not source.strip() or source.lstrip().startswith("#"):
            continue
        match = _ENTRY.match(source)
        if match is None:
            continue
        key = match["key"]
        if key in first_seen:
            duplicates.append(
                Duplicate(key=key, line=number, first_line=first_seen[key])
            )
            continue
        first_seen[key] = number
        entries.append(Entry(key=key, line=number, ignored=IGNORE_MARKER in source))
    return ExampleFile(path=path, entries=tuple(entries), duplicates=tuple(duplicates))
