"""Command line entry point."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from . import __version__, report
from .checker import check
from .discovery import find_repo_root, repo_files
from .sources import Collected, GenericSource, collect

EXIT_OK = 0
EXIT_FINDINGS = 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-version-consistency",
        description=(
            "Check that every version declared across the project's manifests, "
            "sources and changelog is the same one."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--canonical",
        metavar="PATH",
        help="the source of truth other declarations must match",
    )
    parser.add_argument(
        "--exclude",
        metavar="GLOB",
        action="append",
        default=[],
        help="skip files matching this glob; repeatable",
    )
    parser.add_argument(
        "--source",
        metavar="GLOB:REGEX",
        action="append",
        default=[],
        help=(
            "read a version from another format, with a (?P<version>...) "
            "group; repeatable"
        ),
    )
    parser.add_argument(
        "--ignore-value",
        metavar="VERSION",
        action="append",
        default=[],
        help="treat this value as a placeholder; repeatable",
    )
    parser.add_argument(
        "--changelog",
        choices=("strict", "lenient", "off"),
        default="lenient",
        help=(
            "lenient (default) lets the changelog sit behind while an "
            "Unreleased section is open; strict requires an exact match"
        ),
    )
    parser.add_argument(
        "--check-tag",
        action="store_true",
        help="also fail when the latest git tag is ahead of the declared version",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print the summary line only"
    )
    return parser


def _parse_sources(raw: Sequence[str]) -> list[GenericSource]:
    sources: list[GenericSource] = []
    for item in raw:
        glob, separator, expression = item.partition(":")
        if not separator or not expression or not glob:
            raise ValueError(f"--source {item!r}: expected GLOB:REGEX")
        try:
            pattern = re.compile(expression)
        except re.error as error:
            raise ValueError(f"--source {item!r}: {error}") from error
        if "version" not in pattern.groupindex and not pattern.groups:
            raise ValueError(
                f"--source {item!r}: needs a (?P<version>...) or a capturing group"
            )
        sources.append(GenericSource(glob=glob, pattern=pattern))
    return sources


def _latest_tag(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ("git", "describe", "--tags", "--abbrev=0"),
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip().removeprefix("v") or None


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        sources = _parse_sources(args.source)
    except ValueError as error:
        parser.error(str(error))

    root = find_repo_root(Path.cwd())
    files = repo_files(root, excludes=args.exclude)
    collected = collect(root, files, generic=sources)

    if args.ignore_value:
        ignored = set(args.ignore_value)
        collected = Collected(
            manifests=tuple(
                item for item in collected.manifests if item.version not in ignored
            ),
            changelog=collected.changelog,
        )

    result = check(
        collected,
        canonical=args.canonical,
        changelog_mode=args.changelog,
        tag=_latest_tag(root) if args.check_tag else None,
    )
    if result.ok:
        return EXIT_OK

    if args.quiet:
        print(report.summarize(result))
    else:
        print(report.render(result, color=report.use_color()))
    return EXIT_FINDINGS
