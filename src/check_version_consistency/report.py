"""Render the whole picture, not only the parts that are wrong.

Knowing that ``__init__.py`` says 1.3.2 is not much use on its own; what tells
you which side to fix is seeing that everything else says 1.4.0. So every
declaration is listed, and the failing ones are marked.
"""

from __future__ import annotations

import os
import sys

from .checker import Report

_BOLD = "\033[1m"
_RED = "\033[31m"
_RESET = "\033[0m"


def use_color(stream: object | None = None) -> bool:
    """Colour only when a human is watching, and never against NO_COLOR."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    target = stream if stream is not None else sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def _paint(text: str, code: str, *, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def render(report: Report, *, color: bool = False) -> str:
    if report.ok:
        return ""

    messages = {
        (finding.declaration.path, finding.declaration.line): finding.message
        for finding in report.findings
    }

    rows = list(report.declarations)
    seen = {(item.path, item.line) for item in rows}
    # A git tag is a finding without being a declaration in the tree.
    rows += [
        finding.declaration
        for finding in report.findings
        if (finding.declaration.path, finding.declaration.line) not in seen
    ]

    def where(declaration) -> str:
        if declaration.line:
            return f"{declaration.path}:{declaration.line}"
        return str(declaration.path)

    distinct = len({item.version for item in rows})
    version_width = max(len(item.version) for item in rows)
    where_width = max(len(where(item)) for item in rows)

    lines = [
        _paint(
            f"The project declares {distinct} different versions:", _BOLD, color=color
        ),
        "",
    ]
    for declaration in rows:
        message = messages.get((declaration.path, declaration.line))
        marker = _paint(f"  <- {message}", _RED, color=color) if message else ""
        lines.append(
            f"  {declaration.version.ljust(version_width)}  "
            f"{where(declaration).ljust(where_width)}  {declaration.detail}{marker}"
        )

    lines.append("")
    if report.expected is not None:
        lines.append(
            _paint(f"Expected {report.expected} everywhere.", _RED, color=color)
        )
    return "\n".join(lines)


def summarize(report: Report) -> str:
    """Return the one-line form used by --quiet."""
    if report.ok:
        return ""
    total = len(report.findings)
    noun = "declaration" if total == 1 else "declarations"
    expected = f" (expected {report.expected})" if report.expected else ""
    return f"{total} disagreeing {noun}{expected}"
