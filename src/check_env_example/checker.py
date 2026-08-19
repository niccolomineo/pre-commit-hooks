"""Compare what the code reads against what the example file documents."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .example_file import Duplicate, Entry, ExampleFile
from .extractors import Reference

# Variables the tool deliberately holds no opinion about: the operating system,
# the shell, the CI runner or a well-known runtime supplies and consumes them,
# so neither half of the check applies. Documenting PYTHONDEVMODE is a fair
# thing to do, and so is leaving it out.
DEFAULT_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "PWD",
        "OLDPWD",
        "SHELL",
        "TERM",
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "TZ",
        "TMPDIR",
        "TEMP",
        "TMP",
        "HOSTNAME",
        "EDITOR",
        "VISUAL",
        "SSH_AUTH_SOCK",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "CI",
        "NO_COLOR",
        "FORCE_COLOR",
        # Read by the interpreter itself, never by your code.
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONBREAKPOINT",
        "PYTHONDEVMODE",
        "PYTHONTRACEMALLOC",
        "PYTHONWARNINGS",
        "PYTHONHASHSEED",
        "VIRTUAL_ENV",
        "NODE_ENV",
        # Read by the Docker tooling itself.
        "COMPOSE_FILE",
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_PROFILES",
        "DOCKER_HOST",
        "DOCKER_BUILDKIT",
        # import.meta.env built-ins, injected by the bundler rather than by you.
        "MODE",
        "DEV",
        "PROD",
        "SSR",
        "BASE_URL",
    }
)
DEFAULT_ALLOWED_PREFIXES = ("GITHUB_", "RUNNER_", "GITLAB_", "CI_")


@dataclass(frozen=True, slots=True)
class Missing:
    """A variable the code reads that the example file does not document."""

    var: str
    first: Reference
    occurrences: int


@dataclass(frozen=True, slots=True)
class Report:
    missing: tuple[Missing, ...]
    unused: tuple[Entry, ...]
    duplicates: tuple[Duplicate, ...]

    @property
    def ok(self) -> bool:
        return not (self.missing or self.unused or self.duplicates)


def is_allowed(var: str, allowlist: Iterable[str], prefixes: Sequence[str]) -> bool:
    return var in set(allowlist) or var.startswith(tuple(prefixes))


def check(
    *,
    example: ExampleFile,
    references: Sequence[Reference],
    allowlist: Iterable[str] = DEFAULT_ALLOWLIST,
    allowed_prefixes: Sequence[str] = DEFAULT_ALLOWED_PREFIXES,
    report_unused: bool = True,
) -> Report:
    """Cross the two sides and return everything that does not line up."""
    documented = example.by_key()
    allowed = set(allowlist)

    grouped: dict[str, list[Reference]] = {}
    for reference in references:
        grouped.setdefault(reference.var, []).append(reference)

    missing = tuple(
        Missing(var=var, first=found[0], occurrences=len(found))
        for var, found in sorted(grouped.items())
        if var not in documented and not is_allowed(var, allowed, allowed_prefixes)
    )

    # The allowlist applies in both directions. An allowed variable is one the
    # tool does not reason about, so documenting it is no more of an error than
    # leaving it out: PYTHONDEVMODE belongs in the example file for a human to
    # set, and no line of code will ever read it.
    unused: tuple[Entry, ...] = ()
    if report_unused:
        unused = tuple(
            entry
            for entry in example.entries
            if not entry.ignored
            and entry.key not in grouped
            and not is_allowed(entry.key, allowed, allowed_prefixes)
        )

    return Report(missing=missing, unused=unused, duplicates=example.duplicates)
