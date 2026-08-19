"""Append the variables the code reads but nobody documented."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .checker import Missing


def append_missing(text: str, missing: Sequence[Missing]) -> str:
    """Return ``text`` with an entry per missing variable added at the end.

    Existing lines are never touched and nothing is reordered: the point is to
    hand back a diff that is obvious to review, not to reformat the file.
    """
    if not missing:
        return text

    body = text
    if body and not body.endswith("\n"):
        body += "\n"
    if body.strip():
        body += "\n"

    added = [
        line
        for item in missing
        for line in (
            f"# used in {item.first.path}:{item.first.line}",
            f"{item.var}=",
        )
    ]
    return body + "\n".join(added) + "\n"


def apply(path: Path, text: str, missing: Sequence[Missing]) -> bool:
    """Write the fixed file. Returns whether anything changed."""
    fixed = append_missing(text, missing)
    if fixed == text:
        return False
    path.write_text(fixed, encoding="utf-8")
    return True
