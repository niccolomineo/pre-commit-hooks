"""Just enough version ordering to tell "behind" from "ahead".

Nothing here tries to be PEP 440 or SemVer: the only question ever asked is
whether one version of the *same* project comes before another, and for that a
numeric release tuple plus "a suffix sorts below the bare release" is enough.
"""

from __future__ import annotations

import re

_RELEASE = re.compile(r"^(?P<release>\d+(?:\.\d+)*)(?P<rest>.*)$")


def sort_key(version: str) -> tuple[tuple[int, ...], int, str]:
    """Return a key ordering versions of one project against each other."""
    match = _RELEASE.match(version)
    if match is None:
        return ((), 0, version)
    numbers = [int(part) for part in match["release"].split(".")]
    # 1.4 and 1.4.0 are the same release, so trailing zeros must not decide it.
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    rest = match["rest"]
    # 1.4.0rc1 comes before 1.4.0.
    return (tuple(numbers), 0 if rest else 1, rest)


def is_behind(version: str, other: str) -> bool:
    """Report whether ``version`` comes strictly before ``other``."""
    return sort_key(version) < sort_key(other)
