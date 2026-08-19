"""Locate the files to scan, independently of how the hook was invoked.

The hook declares ``pass_filenames: false``, so a commit-time run and a
``--all-files`` run must see exactly the same set of files. Comparing versions
only makes sense with every manifest in view at once, and pre-commit stashes
unstaged changes before running hooks, so reading the working tree after asking
git for the index yields the content that is about to be committed.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

# Only used when the tool runs outside a git repository: inside one, git's own
# ignore rules are the authority on what belongs to the project.
ALWAYS_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "target",
        ".next",
        "htmlcov",
    }
)


def find_repo_root(start: Path) -> Path:
    """Return the git top level containing ``start``, or ``start`` itself."""
    try:
        completed = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            cwd=start,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return start
    top_level = completed.stdout.strip()
    return Path(top_level) if top_level else start


def _indexed_files(root: Path) -> list[Path] | None:
    """Return the paths in git's index, or None when git is unavailable.

    The index -- not the working tree -- is what is about to be committed: a
    file staged for deletion is gone from it, and a newly added one is in it.
    """
    try:
        completed = subprocess.run(
            ("git", "ls-files", "-z", "--cached", "--full-name"),
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [Path(name) for name in completed.stdout.split("\0") if name]


def _walked_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for current, directories, names in os.walk(root):
        directories[:] = [
            name for name in directories if name not in ALWAYS_EXCLUDED_DIRS
        ]
        base = Path(current)
        found.extend((base / name).relative_to(root) for name in names)
    return found


def repo_files(root: Path, *, excludes: Iterable[str] = ()) -> list[Path]:
    """Return every project file, as paths relative to ``root``."""
    indexed = _indexed_files(root)
    candidates = indexed if indexed is not None else _walked_files(root)
    patterns = tuple(excludes)
    kept = [
        relative
        for relative in candidates
        if not _is_excluded(relative, patterns) and (root / relative).is_file()
    ]
    return sorted(kept)


def _is_excluded(relative: Path, patterns: tuple[str, ...]) -> bool:
    posix = relative.as_posix()
    return any(
        fnmatch(posix, pattern) or fnmatch(relative.name, pattern)
        for pattern in patterns
    )


def read_text(path: Path) -> str | None:
    """Return the text of ``path``, or None when it is binary or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
