"""Command line entry point."""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from pathlib import Path

from . import __version__, example_file, fixer, report
from .checker import DEFAULT_ALLOWED_PREFIXES, DEFAULT_ALLOWLIST, Report, check
from .discovery import find_repo_root, read_text, repo_files
from .extractors import Reference, extract, is_scannable

EXIT_OK = 0
EXIT_FINDINGS = 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-env-example",
        description=(
            "Check that every environment variable read by the code is "
            "documented in .env.example, and that every documented variable "
            "is actually read."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--example-file",
        metavar="PATH",
        help=(
            "the file documenting the variables; by default the first of "
            + ", ".join(example_file.CANDIDATE_NAMES)
        ),
    )
    parser.add_argument(
        "--ignore",
        metavar="VAR",
        action="append",
        default=[],
        help="never report this variable; repeatable",
    )
    parser.add_argument(
        "--exclude",
        metavar="GLOB",
        action="append",
        default=[],
        help="skip files matching this glob; repeatable",
    )
    parser.add_argument(
        "--extra-pattern",
        metavar="EXT:REGEX",
        action="append",
        default=[],
        help=(
            "additional pattern for one extension, with a (?P<var>...) group, "
            "for framework helpers such as django-environ; repeatable"
        ),
    )
    parser.add_argument(
        "--no-unused",
        action="store_true",
        help="do not report documented variables that the code never reads",
    )
    parser.add_argument(
        "--no-default-allowlist",
        action="store_true",
        help="also report the OS and CI variables allowed by default",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="append the missing variables to the example file",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print the summary line only"
    )
    return parser


def _parse_extra_patterns(raw: Sequence[str]) -> dict[str, list[re.Pattern[str]]]:
    patterns: dict[str, list[re.Pattern[str]]] = {}
    for item in raw:
        extension, separator, expression = item.partition(":")
        if not separator or not expression:
            raise ValueError(f"--extra-pattern {item!r}: expected EXT:REGEX")
        if not extension.startswith("."):
            extension = f".{extension}"
        try:
            compiled = re.compile(expression)
        except re.error as error:
            raise ValueError(f"--extra-pattern {item!r}: {error}") from error
        if "var" not in compiled.groupindex:
            raise ValueError(f"--extra-pattern {item!r}: missing a (?P<var>...) group")
        patterns.setdefault(extension, []).append(compiled)
    return patterns


def _collect(
    root: Path,
    files: Sequence[Path],
    extra_patterns: dict[str, list[re.Pattern[str]]],
) -> list[Reference]:
    references: list[Reference] = []
    for relative in files:
        if not is_scannable(relative, extra_patterns):
            continue
        text = read_text(root / relative)
        if text is None:
            continue
        references.extend(extract(relative, text, extra_patterns))
    return references


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        extra_patterns = _parse_extra_patterns(args.extra_pattern)
    except ValueError as error:
        parser.error(str(error))

    root = find_repo_root(Path.cwd())

    if args.example_file:
        example_path = Path(args.example_file)
        if not example_path.is_file():
            parser.error(f"{args.example_file}: no such file")
    else:
        discovered = example_file.discover(root)
        if discovered is None:
            # A project without an example file has nothing to keep in sync.
            return EXIT_OK
        example_path = discovered

    example_text = read_text(example_path)
    if example_text is None:
        parser.error(f"{example_path}: cannot be read")
    example = example_file.parse(example_path, example_text)

    files = repo_files(root, excludes=args.exclude)
    references = _collect(root, files, extra_patterns)

    allowlist = set() if args.no_default_allowlist else set(DEFAULT_ALLOWLIST)
    allowlist.update(args.ignore)
    prefixes = () if args.no_default_allowlist else DEFAULT_ALLOWED_PREFIXES

    result = check(
        example=example,
        references=references,
        allowlist=allowlist,
        allowed_prefixes=prefixes,
        report_unused=not args.no_unused,
    )
    if result.ok:
        return EXIT_OK

    relative_example = _relative_to(example_path, root)
    if args.fix and result.missing:
        fixer.apply(example_path, example_text, result.missing)
        print(
            f"{relative_example}: added {len(result.missing)} missing "
            f"{'variable' if len(result.missing) == 1 else 'variables'}"
        )
        result = Report(missing=(), unused=result.unused, duplicates=result.duplicates)
        if result.ok:
            return EXIT_FINDINGS

    if args.quiet:
        print(report.summarize(result))
    else:
        print(report.render(result, relative_example, color=report.use_color()))
    return EXIT_FINDINGS


def _relative_to(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path
