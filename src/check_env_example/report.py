"""Render findings as ``path:line`` lines a terminal can turn into links."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .checker import Report

_BOLD = "\033[1m"
_RED = "\033[31m"
_RESET = "\033[0m"


def use_color(stream: object | None = None) -> bool:
    """Colour only when a human is watching, and never against NO_COLOR."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def _paint(text: str, code: str, *, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def _section(title: str, rows: list[tuple[str, str]], *, color: bool) -> list[str]:
    if not rows:
        return []
    width = max(len(name) for name, _ in rows)
    lines = [_paint(title, _BOLD, color=color)]
    lines.extend(f"  {name.ljust(width)}  {detail}" for name, detail in rows)
    lines.append("")
    return lines


def render(report: Report, example: Path, *, color: bool = False) -> str:
    """Return the full human-readable output for a failing run."""
    if report.ok:
        return ""

    lines: list[str] = []
    lines += _section(
        f"Read by the code, missing from {example}:",
        [
            (
                item.var,
                f"{item.first.path}:{item.first.line}"
                + (f"  (+{item.occurrences - 1} more)" if item.occurrences > 1 else ""),
            )
            for item in report.missing
        ],
        color=color,
    )
    lines += _section(
        f"In {example}, never read by the code:",
        [(entry.key, f"{example}:{entry.line}") for entry in report.unused],
        color=color,
    )
    lines += _section(
        f"Declared twice in {example}:",
        [
            (item.key, f"{example}:{item.line}  (first at line {item.first_line})")
            for item in report.duplicates
        ],
        color=color,
    )

    lines.append(_paint(summarize(report), _RED, color=color))
    return "\n".join(lines)


def summarize(report: Report) -> str:
    """Return the one-line form used by --quiet."""
    counts = (
        (len(report.missing), "missing"),
        (len(report.unused), "unused"),
        (len(report.duplicates), "duplicate"),
    )
    return ", ".join(f"{total} {label}" for total, label in counts if total)
